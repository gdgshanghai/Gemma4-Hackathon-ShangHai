platform :ios, '13.0'

# CocoaPods analytics sends network stats synchronously affecting flutter build latency.
ENV['COCOAPODS_DISABLE_STATS'] = 'true'

project 'Runner', {
  'Debug' => :debug,
  'Profile' => :release,
  'Release' => :release,
}

def flutter_root
  generated_xcode_build_settings_path = File.expand_path(File.join('..', 'Flutter', 'Generated.xcconfig'), __FILE__)
  unless File.exist?(generated_xcode_build_settings_path)
    raise "#{generated_xcode_build_settings_path} must exist. If you're running pod install manually, make sure flutter pub get is executed first"
  end

  File.foreach(generated_xcode_build_settings_path) do |line|
    matches = line.match(/FLUTTER_ROOT\=(.*)/)
    return matches[1].strip if matches
  end
  raise "FLUTTER_ROOT not found in #{generated_xcode_build_settings_path}. Try deleting Generated.xcconfig, then run flutter pub get"
end

require File.expand_path(File.join('packages', 'flutter_tools', 'bin', 'podhelper'), flutter_root)

flutter_ios_podfile_setup

target 'Runner' do
  # Prefer static linkage for Flutter plugins to avoid "Module not found" issues.
  use_frameworks! :linkage => :static

  # Suppress warnings from all pods (including flutter_tts) to keep build logs clean
  inhibit_all_warnings!

  flutter_install_all_ios_pods File.dirname(File.realpath(__FILE__))
  target 'RunnerTests' do
    inherit! :search_paths
  end
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
    
    target.build_configurations.each do |config|
      # 解决 objective_c.framework 缺失 dSYM 的问题：强制生成 dSYM 文件
      config.build_settings['DEBUG_INFORMATION_FORMAT'] = 'dwarf-with-dsym'
      # 显式启用调试符号生成
      config.build_settings['GCC_GENERATE_DEBUGGING_SYMBOLS'] = 'YES'
      # 确保符号在打包时不被剥离，以便生成完整的 DWARF 文件供 Archive 校验
      config.build_settings['STRIP_INSTALLED_PRODUCT'] = 'NO'
      # 禁止在复制阶段剥离符号
      config.build_settings['COPY_PHASE_STRIP'] = 'NO'
      # 设置剥离风格为调试，保留更多符号信息
      config.build_settings['STRIP_STYLE'] = 'debugging'
      # 确保所有 Pod 的部署目标与项目设置 (13.0) 保持一致
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '13.0'
      # 显式关闭 Bitcode 以解决 dSYM 校验失败及与第三方库符号冲突的问题
      config.build_settings['ENABLE_BITCODE'] = 'NO'
    end
  end
end
