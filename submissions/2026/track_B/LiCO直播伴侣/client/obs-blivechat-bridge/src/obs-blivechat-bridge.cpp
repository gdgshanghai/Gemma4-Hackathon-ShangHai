#include <obs-module.h>
#include <obs-frontend-api.h>
#include <media-io/audio-io.h>

#include <curl/curl.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <ctime>
#include <deque>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

OBS_DECLARE_MODULE()
OBS_MODULE_USE_DEFAULT_LOCALE("obs-blivechat-bridge", "en-US")

namespace {

const char *BACKEND_BASE_URL = "http://127.0.0.1:12450";
const uint32_t AUDIO_SAMPLE_RATE = 16000;
const uint16_t AUDIO_CHANNELS = 1;
const size_t AUDIO_REPORT_FRAMES = AUDIO_SAMPLE_RATE * 5;
const size_t MAX_SCREENSHOT_FILES = 5;

// OBS UI Track 1 = mix index 0 (mixed fallback)
// OBS UI Track 2 = mix index 1 (microphone)
// OBS UI Track 3 = mix index 2 (desktop audio)
const size_t MIXED_TRACK_IDX = 0;
const size_t MIC_TRACK_IDX = 1;
const size_t DESKTOP_TRACK_IDX = 2;

std::atomic_bool streaming_active{false};
std::atomic_bool split_audio_enabled{false};
std::atomic_bool audio_capture_active{false};
std::atomic_bool split_audio_config_loaded{false};
std::chrono::steady_clock::time_point last_screenshot_at;
std::chrono::steady_clock::time_point stream_started_at;
std::time_t stream_started_unix = 0;
std::mutex http_mutex;
std::mutex screenshot_mutex;
std::deque<std::string> screenshot_files;
struct audio_convert_info audio_conversion = {AUDIO_SAMPLE_RATE, AUDIO_FORMAT_FLOAT, SPEAKERS_MONO, false};

struct AudioTrackCapture {
	const char *track_role;
	size_t mix_idx;
	std::mutex mutex;
	std::vector<int16_t> samples;
	double sum_squares = 0.0;
	double peak = 0.0;
	uint64_t frame_count = 0;
};

AudioTrackCapture mixed_capture{"mixed", MIXED_TRACK_IDX};
AudioTrackCapture mic_capture{"mic", MIC_TRACK_IDX};
AudioTrackCapture desktop_capture{"desktop", DESKTOP_TRACK_IDX};

std::string json_escape(const std::string &value)
{
	std::ostringstream escaped;
	for (char ch : value) {
		switch (ch) {
		case '\\':
			escaped << "\\\\";
			break;
		case '"':
			escaped << "\\\"";
			break;
		case '\n':
			escaped << "\\n";
			break;
		case '\r':
			escaped << "\\r";
			break;
		case '\t':
			escaped << "\\t";
			break;
		default:
			escaped << ch;
			break;
		}
	}
	return escaped.str();
}

std::string base64_encode(const uint8_t *data, size_t len)
{
	static const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	std::string out;
	out.reserve(((len + 2) / 3) * 4);
	for (size_t i = 0; i < len; i += 3) {
		uint32_t value = data[i] << 16;
		if (i + 1 < len)
			value |= data[i + 1] << 8;
		if (i + 2 < len)
			value |= data[i + 2];

		out.push_back(table[(value >> 18) & 0x3F]);
		out.push_back(table[(value >> 12) & 0x3F]);
		out.push_back(i + 1 < len ? table[(value >> 6) & 0x3F] : '=');
		out.push_back(i + 2 < len ? table[value & 0x3F] : '=');
	}
	return out;
}

void append_le16(std::vector<uint8_t> &out, uint16_t value)
{
	out.push_back(static_cast<uint8_t>(value & 0xFF));
	out.push_back(static_cast<uint8_t>((value >> 8) & 0xFF));
}

void append_le32(std::vector<uint8_t> &out, uint32_t value)
{
	out.push_back(static_cast<uint8_t>(value & 0xFF));
	out.push_back(static_cast<uint8_t>((value >> 8) & 0xFF));
	out.push_back(static_cast<uint8_t>((value >> 16) & 0xFF));
	out.push_back(static_cast<uint8_t>((value >> 24) & 0xFF));
}

std::string build_wav_base64(const std::vector<int16_t> &samples)
{
	uint32_t data_size = static_cast<uint32_t>(samples.size() * sizeof(int16_t));
	uint32_t byte_rate = AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * sizeof(int16_t);
	uint16_t block_align = AUDIO_CHANNELS * sizeof(int16_t);

	std::vector<uint8_t> wav;
	wav.reserve(44 + data_size);
	wav.insert(wav.end(), {'R', 'I', 'F', 'F'});
	append_le32(wav, 36 + data_size);
	wav.insert(wav.end(), {'W', 'A', 'V', 'E'});
	wav.insert(wav.end(), {'f', 'm', 't', ' '});
	append_le32(wav, 16);
	append_le16(wav, 1);
	append_le16(wav, AUDIO_CHANNELS);
	append_le32(wav, AUDIO_SAMPLE_RATE);
	append_le32(wav, byte_rate);
	append_le16(wav, block_align);
	append_le16(wav, 16);
	wav.insert(wav.end(), {'d', 'a', 't', 'a'});
	append_le32(wav, data_size);
	const uint8_t *pcm = reinterpret_cast<const uint8_t *>(samples.data());
	wav.insert(wav.end(), pcm, pcm + data_size);
	return base64_encode(wav.data(), wav.size());
}

size_t curl_write_discard(char *ptr, size_t size, size_t nmemb, void *userdata)
{
	(void)userdata;
	(void)ptr;
	return size * nmemb;
}

size_t curl_write_to_string(char *ptr, size_t size, size_t nmemb, void *userdata)
{
	auto *out = static_cast<std::string *>(userdata);
	size_t total = size * nmemb;
	if (total > 0)
		out->append(ptr, total);
	return total;
}

bool parse_json_bool_true(const std::string &json, const char *key)
{
	const std::string needle = std::string("\"") + key + "\"";
	size_t pos = json.find(needle);
	if (pos == std::string::npos)
		return false;
	pos += needle.size();
	while (pos < json.size() && (json[pos] == ':' || json[pos] == ' ' || json[pos] == '\t'))
		pos++;
	return pos + 4 <= json.size() && json.compare(pos, 4, "true") == 0;
}

bool http_get(const char *path, std::string *response, long *http_code = nullptr)
{
	std::lock_guard<std::mutex> lock(http_mutex);
	std::string response_body;

	CURL *curl = curl_easy_init();
	if (!curl)
		return false;

	std::string url = std::string(BACKEND_BASE_URL) + path;
	curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
	curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_to_string);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_body);
	curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 5000L);
	curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 3000L);
	curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

	CURLcode code = curl_easy_perform(curl);
	long status = 0;
	curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
	curl_easy_cleanup(curl);

	if (response)
		*response = std::move(response_body);
	if (http_code)
		*http_code = status;

	return code == CURLE_OK && status >= 200 && status < 300;
}

bool http_post_json(const char *path, const std::string &body, long *http_code = nullptr)
{
	std::lock_guard<std::mutex> lock(http_mutex);
	std::string post_body = body;

	CURL *curl = curl_easy_init();
	if (!curl)
		return false;

	std::string url = std::string(BACKEND_BASE_URL) + path;
	struct curl_slist *headers = curl_slist_append(nullptr, "Content-Type: application/json");
	if (!headers) {
		curl_easy_cleanup(curl);
		return false;
	}

	curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
	curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
	curl_easy_setopt(curl, CURLOPT_POST, 1L);
	curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_body.c_str());
	if (post_body.size() <= static_cast<size_t>(LONG_MAX)) {
		curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(post_body.size()));
	}
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_discard);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, nullptr);
	curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 30000L);
	curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 3000L);
	curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

	CURLcode code = curl_easy_perform(curl);
	long status = 0;
	curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);

	if (code != CURLE_OK) {
		blog(LOG_WARNING, "[obs-blivechat-bridge] POST %s failed: %s (http=%ld, bytes=%zu)", path,
		     curl_easy_strerror(code), status, post_body.size());
	} else if (status < 200 || status >= 300) {
		blog(LOG_WARNING, "[obs-blivechat-bridge] POST %s http %ld (bytes=%zu)", path, status,
		     post_body.size());
	}

	curl_slist_free_all(headers);
	curl_easy_cleanup(curl);

	if (http_code)
		*http_code = status;
	return code == CURLE_OK && status >= 200 && status < 300;
}

void post_json(const char *path, const std::string &body)
{
	(void)http_post_json(path, body, nullptr);
}

bool fetch_split_audio_enabled()
{
	std::string response;
	long http_code = 0;
	if (!http_get("/api/obs/config", &response, &http_code)) {
		blog(LOG_WARNING,
		     "[obs-blivechat-bridge] GET /api/obs/config failed (http=%ld). Start blivechat backend and enable split tracks in Home settings.",
		     http_code);
		return false;
	}

	const bool enabled = parse_json_bool_true(response, "splitAudioTracks");
	blog(LOG_INFO, "[obs-blivechat-bridge] splitAudioTracks=%s", enabled ? "true" : "false");
	return enabled;
}

void reload_split_audio_config()
{
	split_audio_enabled = fetch_split_audio_enabled();
	split_audio_config_loaded = true;
}

int64_t current_stream_duration_seconds()
{
	if (!streaming_active || stream_started_unix == 0)
		return 0;
	auto now = std::chrono::steady_clock::now();
	return std::chrono::duration_cast<std::chrono::seconds>(now - stream_started_at).count();
}

void post_stream_event(const char *type, bool active, int64_t duration_seconds = 0, const char *recording_file_path = nullptr)
{
	std::ostringstream body;
	body << "{\"type\":\"" << type << "\",\"streamingActive\":" << (active ? "true" : "false")
	     << ",\"streamStartedAt\":" << static_cast<long long>(stream_started_unix)
	     << ",\"streamDurationSeconds\":" << duration_seconds;
	if (recording_file_path && *recording_file_path) {
		body << ",\"recordingFilePath\":\"" << json_escape(recording_file_path) << "\"";
	}
	body << "}";
	post_json("/api/obs/event", body.str());
}

void post_recording_stopped_event(const char *recording_file_path)
{
	if (!recording_file_path || !*recording_file_path)
		return;
	std::ostringstream body;
	body << "{\"type\":\"recording_stopped\",\"recordingFilePath\":\""
	     << json_escape(recording_file_path) << "\"}";
	post_json("/api/obs/event", body.str());
}

void post_screenshot_path(const char *path)
{
	if (!path || !*path)
		return;
	std::string screenshot_path(path);
	{
		std::lock_guard<std::mutex> lock(screenshot_mutex);
		screenshot_files.erase(std::remove(screenshot_files.begin(), screenshot_files.end(), screenshot_path), screenshot_files.end());
		screenshot_files.push_back(screenshot_path);
		while (screenshot_files.size() > MAX_SCREENSHOT_FILES) {
			std::string stale_path = screenshot_files.front();
			screenshot_files.pop_front();
			if (!stale_path.empty() && std::remove(stale_path.c_str()) != 0) {
				blog(LOG_DEBUG,
				     "[obs-blivechat-bridge] remove stale screenshot skipped (file busy or gone): %s",
				     stale_path.c_str());
			}
		}
	}

	std::ostringstream body;
	body << "{\"sourceName\":\"OBS Program\",\"imageFormat\":\"file\","
	     << "\"imageFilePath\":\"" << json_escape(path) << "\","
	     << "\"summary\":\"OBS screenshot saved for stream monitoring\"}";
	post_json("/api/obs/frame", body.str());
}

void post_audio_clip(const std::vector<int16_t> &samples, double rms, double peak, double duration_seconds,
		     const char *track_role, size_t mix_idx)
{
	if (samples.empty())
		return;

	std::ostringstream body;
	body << std::fixed << std::setprecision(6)
	     << "{\"trackRole\":\"" << track_role << "\",\"mixIdx\":" << mix_idx
	     << ",\"level\":" << rms << ",\"rms\":" << rms << ",\"peak\":" << peak
	     << ",\"sampleRate\":" << AUDIO_SAMPLE_RATE << ",\"channels\":" << AUDIO_CHANNELS
	     << ",\"audioFormat\":\"wav\",\"durationSeconds\":" << duration_seconds
	     << ",\"audioData\":\"" << build_wav_base64(samples) << "\"}";
	post_json("/api/obs/audio", body.str());
}

void reset_audio_capture(AudioTrackCapture &capture)
{
	std::lock_guard<std::mutex> lock(capture.mutex);
	capture.samples.clear();
	capture.sum_squares = 0.0;
	capture.peak = 0.0;
	capture.frame_count = 0;
}

void reset_all_audio_captures()
{
	reset_audio_capture(mixed_capture);
	reset_audio_capture(mic_capture);
	reset_audio_capture(desktop_capture);
}

void flush_audio_capture(AudioTrackCapture &capture)
{
	std::vector<int16_t> samples_to_post;
	double rms = 0.0;
	double peak = 0.0;
	uint64_t frames = 0;
	const char *track_role = capture.track_role;
	size_t mix_idx = capture.mix_idx;
	{
		std::lock_guard<std::mutex> lock(capture.mutex);
		if (capture.frame_count == 0)
			return;
		samples_to_post.swap(capture.samples);
		frames = capture.frame_count;
		rms = std::sqrt(capture.sum_squares / static_cast<double>(capture.frame_count));
		peak = capture.peak;
		capture.sum_squares = 0.0;
		capture.peak = 0.0;
		capture.frame_count = 0;
	}
	post_audio_clip(samples_to_post, rms, peak, static_cast<double>(frames) / AUDIO_SAMPLE_RATE, track_role, mix_idx);
}

void flush_all_audio_captures()
{
	if (split_audio_enabled.load()) {
		flush_audio_capture(mic_capture);
		flush_audio_capture(desktop_capture);
	} else {
		flush_audio_capture(mixed_capture);
	}
}

void audio_callback(void *param, size_t, struct audio_data *data)
{
	if (!streaming_active || !data || !data->data[0] || data->frames == 0)
		return;

	auto *capture = static_cast<AudioTrackCapture *>(param);
	if (capture == nullptr)
		return;

	const float *samples = reinterpret_cast<const float *>(data->data[0]);
	bool should_post = false;
	{
		std::lock_guard<std::mutex> lock(capture->mutex);
		capture->samples.reserve(AUDIO_REPORT_FRAMES);
		for (uint32_t i = 0; i < data->frames; i++) {
			double sample = std::clamp(static_cast<double>(samples[i]), -1.0, 1.0);
			double abs_sample = std::abs(sample);
			capture->sum_squares += sample * sample;
			if (abs_sample > capture->peak)
				capture->peak = abs_sample;
			capture->samples.push_back(static_cast<int16_t>(sample * 32767.0));
			capture->frame_count++;
		}
		should_post = capture->frame_count >= AUDIO_REPORT_FRAMES;
	}
	if (should_post)
		flush_audio_capture(*capture);
}

void start_audio_capture()
{
	if (audio_capture_active.exchange(true))
		return;

	reset_all_audio_captures();
	if (split_audio_enabled.load()) {
		blog(LOG_INFO, "[obs-blivechat-bridge] split audio enabled: mic track=%zu desktop track=%zu",
		     MIC_TRACK_IDX, DESKTOP_TRACK_IDX);
		obs_add_raw_audio_callback(MIC_TRACK_IDX, &audio_conversion, audio_callback, &mic_capture);
		obs_add_raw_audio_callback(DESKTOP_TRACK_IDX, &audio_conversion, audio_callback, &desktop_capture);
	} else {
		blog(LOG_INFO, "[obs-blivechat-bridge] mixed audio enabled: track=%zu", MIXED_TRACK_IDX);
		obs_add_raw_audio_callback(MIXED_TRACK_IDX, &audio_conversion, audio_callback, &mixed_capture);
	}
}

void stop_audio_capture()
{
	if (!audio_capture_active.exchange(false))
		return;

	split_audio_config_loaded = false;
	obs_remove_raw_audio_callback(MIXED_TRACK_IDX, audio_callback, &mixed_capture);
	obs_remove_raw_audio_callback(MIC_TRACK_IDX, audio_callback, &mic_capture);
	obs_remove_raw_audio_callback(DESKTOP_TRACK_IDX, audio_callback, &desktop_capture);
}

void frontend_event(enum obs_frontend_event event, void *)
{
	switch (event) {
	case OBS_FRONTEND_EVENT_STREAMING_STARTED:
		streaming_active = true;
		stream_started_at = std::chrono::steady_clock::now();
		last_screenshot_at = stream_started_at;
		stream_started_unix = std::time(nullptr);
		reset_all_audio_captures();
		reload_split_audio_config();
		post_stream_event("streaming_started", true, 0);
		start_audio_capture();
		break;
	case OBS_FRONTEND_EVENT_STREAMING_STOPPED: {
		int64_t duration_seconds = current_stream_duration_seconds();
		char *last_recording = obs_frontend_get_last_recording();
		post_stream_event("streaming_stopped", false, duration_seconds, last_recording);
		bfree(last_recording);
		streaming_active = false;
		flush_all_audio_captures();
		stream_started_unix = 0;
		stop_audio_capture();
		break;
	}
	case OBS_FRONTEND_EVENT_RECORDING_STOPPED: {
		char *last_recording = obs_frontend_get_last_recording();
		post_recording_stopped_event(last_recording);
		bfree(last_recording);
		break;
	}
	case OBS_FRONTEND_EVENT_SCREENSHOT_TAKEN: {
		char *last_screenshot = obs_frontend_get_last_screenshot();
		post_screenshot_path(last_screenshot);
		bfree(last_screenshot);
		break;
	}
	default:
		break;
	}
}

void tick(void *, float)
{
	if (!streaming_active)
		return;

	auto now = std::chrono::steady_clock::now();
	if (now - last_screenshot_at < std::chrono::seconds(10))
		return;
	last_screenshot_at = now;
	obs_frontend_take_screenshot();
}

} // namespace

bool obs_module_load(void)
{
	curl_global_init(CURL_GLOBAL_DEFAULT);
	last_screenshot_at = std::chrono::steady_clock::now();
	stream_started_at = last_screenshot_at;
	obs_frontend_add_event_callback(frontend_event, nullptr);
	obs_add_tick_callback(tick, nullptr);
	blog(LOG_INFO, "[obs-blivechat-bridge] loaded (build %s %s)", __DATE__, __TIME__);
	return true;
}

void obs_module_unload(void)
{
	obs_remove_tick_callback(tick, nullptr);
	obs_frontend_remove_event_callback(frontend_event, nullptr);
	stop_audio_capture();
	curl_global_cleanup();
	blog(LOG_INFO, "[obs-blivechat-bridge] unloaded");
}
