import https from "node:https";
import net from "node:net";
import tls from "node:tls";

type JsonResponse = {
  ok: boolean;
  status: number;
  text: string;
};

export async function postJsonToGoogleModel(
  url: string,
  body: unknown,
  proxy?: string,
): Promise<JsonResponse> {
  const apiKey = process.env.GEMINI_API_KEY;
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (apiKey) headers["x-goog-api-key"] = apiKey;

  if (!proxy?.startsWith("socks5://")) {
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    return {
      ok: response.ok,
      status: response.status,
      text: await response.text(),
    };
  }

  return postJsonViaSocks5(url, body, proxy, headers);
}

async function postJsonViaSocks5(
  url: string,
  body: unknown,
  proxy: string,
  headers: Record<string, string>,
): Promise<JsonResponse> {
  const target = new URL(url);
  const proxyUrl = new URL(proxy);
  const payload = JSON.stringify(body);

  const agent = new https.Agent();
  agent.createConnection = (options, callback) => {
    if (!callback) return undefined;
    createSocksTlsSocket({
      proxyHost: proxyUrl.hostname,
      proxyPort: Number(proxyUrl.port || 1080),
      targetHost: String(options.host),
      targetPort: Number(options.port || 443),
    })
      .then((socket) => callback(null, socket))
      .catch((error) => callback(error, null as never));
    return undefined;
  };

  return new Promise((resolve, reject) => {
    const request = https.request(
      {
        method: "POST",
        hostname: target.hostname,
        path: `${target.pathname}${target.search}`,
        headers: {
          ...headers,
          "content-length": Buffer.byteLength(payload),
        },
        agent,
      },
      (response) => {
        const chunks: Buffer[] = [];
        response.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          const status = response.statusCode ?? 0;
          resolve({ ok: status >= 200 && status < 300, status, text });
        });
      },
    );

    request.setTimeout(30000, () => {
      request.destroy(new Error("Google model request timed out"));
    });
    request.on("error", reject);
    request.write(payload);
    request.end();
  });
}

async function createSocksTlsSocket({
  proxyHost,
  proxyPort,
  targetHost,
  targetPort,
}: {
  proxyHost: string;
  proxyPort: number;
  targetHost: string;
  targetPort: number;
}) {
  const socket = net.connect(proxyPort, proxyHost);
  await onceConnect(socket);

  socket.write(Buffer.from([0x05, 0x01, 0x00]));
  const greeting = await readExactly(socket, 2);
  if (greeting[0] !== 0x05 || greeting[1] !== 0x00) {
    socket.destroy();
    throw new Error("SOCKS5 proxy does not allow no-auth connections");
  }

  const host = Buffer.from(targetHost);
  const request = Buffer.concat([
    Buffer.from([0x05, 0x01, 0x00, 0x03, host.length]),
    host,
    Buffer.from([(targetPort >> 8) & 0xff, targetPort & 0xff]),
  ]);
  socket.write(request);

  const head = await readExactly(socket, 4);
  if (head[1] !== 0x00) {
    socket.destroy();
    throw new Error(`SOCKS5 proxy connect failed with code ${head[1]}`);
  }

  const addressLength =
    head[3] === 0x01 ? 4 : head[3] === 0x04 ? 16 : ((await readExactly(socket, 1))[0] ?? 0);
  await readExactly(socket, addressLength + 2);

  return tls.connect({
    socket,
    servername: targetHost,
  });
}

function onceConnect(socket: net.Socket) {
  return new Promise<void>((resolve, reject) => {
    socket.once("connect", resolve);
    socket.once("error", reject);
  });
}

function readExactly(socket: net.Socket, length: number): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let total = 0;

    const cleanup = () => {
      socket.off("data", onData);
      socket.off("error", onError);
    };
    const onError = (error: Error) => {
      cleanup();
      reject(error);
    };
    const onData = (chunk: Buffer) => {
      chunks.push(chunk);
      total += chunk.length;
      if (total < length) return;

      cleanup();
      const buffer = Buffer.concat(chunks, total);
      const needed = buffer.subarray(0, length);
      const rest = buffer.subarray(length);
      if (rest.length) socket.unshift(rest);
      resolve(needed);
    };

    socket.on("data", onData);
    socket.once("error", onError);
  });
}
