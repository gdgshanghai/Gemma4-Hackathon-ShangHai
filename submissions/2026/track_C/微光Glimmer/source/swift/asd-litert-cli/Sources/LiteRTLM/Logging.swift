// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import CLiteRTLM

public enum LiteRTLMLogLevel: Int32 {
  case verbose = 0
  case debug = 1
  case info = 2
  case warning = 3
  case error = 4
  case fatal = 5
  case silent = 1000
}

public func setLiteRTLMMinLogLevel(_ level: LiteRTLMLogLevel) {
  litert_lm_set_min_log_level(level.rawValue)
}
