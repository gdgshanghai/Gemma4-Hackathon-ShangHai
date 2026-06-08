cmake_minimum_required(VERSION 3.28...3.30)

project(obs-blivechat-bridge VERSION 0.1.0)

find_package(libobs QUIET CONFIG)
find_package(obs-frontend-api QUIET CONFIG)
find_package(CURL REQUIRED)

add_library(obs-blivechat-bridge MODULE)

target_sources(obs-blivechat-bridge PRIVATE src/obs-blivechat-bridge.cpp)

if(APPLE AND (NOT TARGET OBS::libobs OR NOT TARGET OBS::frontend-api))
  target_compile_features(obs-blivechat-bridge PRIVATE cxx_std_17)

  set(OBS_STUDIO_SOURCE_DIR "/Users/lico/Desktop/0525project/obs-studio" CACHE PATH "Path to the OBS Studio source tree")

  find_library(OBS_LIBOBS_FRAMEWORK NAMES libobs PATHS "/Applications/OBS.app/Contents/Frameworks" NO_DEFAULT_PATH REQUIRED)
  set(OBS_FRONTEND_API_LIBRARY "/Applications/OBS.app/Contents/Frameworks/obs-frontend-api.dylib")

  if(NOT EXISTS "${OBS_FRONTEND_API_LIBRARY}")
    message(FATAL_ERROR "Could not find OBS frontend API dylib at ${OBS_FRONTEND_API_LIBRARY}")
  endif()

  add_library(OBS::libobs SHARED IMPORTED)
  set_target_properties(OBS::libobs PROPERTIES IMPORTED_LOCATION "${OBS_LIBOBS_FRAMEWORK}")

  add_library(OBS::frontend-api SHARED IMPORTED)
  set_target_properties(OBS::frontend-api PROPERTIES IMPORTED_LOCATION "${OBS_FRONTEND_API_LIBRARY}")

  target_include_directories(
    obs-blivechat-bridge
    PRIVATE
      "${OBS_STUDIO_SOURCE_DIR}/libobs"
      "${OBS_STUDIO_SOURCE_DIR}/frontend/api"
  )

  execute_process(
    COMMAND brew --prefix simde
    OUTPUT_VARIABLE SIMDE_PREFIX
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(EXISTS "${SIMDE_PREFIX}/include/simde/simde-common.h")
    target_include_directories(obs-blivechat-bridge PRIVATE "${SIMDE_PREFIX}/include")
  endif()

  set(OBS_RELEASE_CANDIDATE 0)
  set(OBS_BETA 0)
  configure_file(
    "${OBS_STUDIO_SOURCE_DIR}/libobs/obsconfig.h.in"
    "${CMAKE_CURRENT_BINARY_DIR}/config/obsconfig.h"
    @ONLY
  )

  target_include_directories(obs-blivechat-bridge PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/config")
  target_compile_definitions(obs-blivechat-bridge PRIVATE OBS_INSTALL_PREFIX="")
endif()

target_link_libraries(obs-blivechat-bridge PRIVATE OBS::libobs OBS::frontend-api CURL::libcurl)

set_target_properties(obs-blivechat-bridge PROPERTIES PREFIX "")

if(APPLE)
  set_target_properties(
    obs-blivechat-bridge
    PROPERTIES BUNDLE TRUE
               BUNDLE_EXTENSION plugin
               MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/cmake/macos/Info.plist.in"
  )

  install(TARGETS obs-blivechat-bridge BUNDLE DESTINATION plugins LIBRARY DESTINATION plugins)
else()
  install(TARGETS obs-blivechat-bridge LIBRARY DESTINATION obs-plugins/64bit RUNTIME DESTINATION obs-plugins/64bit)
endif()
