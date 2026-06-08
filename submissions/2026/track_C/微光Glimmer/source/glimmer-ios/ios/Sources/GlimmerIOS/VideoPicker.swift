#if canImport(UIKit)
import SwiftUI
import PhotosUI
import UIKit

/// 系统拍摄视频（UIImagePickerController.camera，仅真机可用）。
struct CameraVideoPicker: UIViewControllerRepresentable {
    let onComplete: (URL?) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let vc = UIImagePickerController()
        vc.sourceType = .camera
        // mediaTypes 必须从 availableMediaTypes 取交集，否则真机会 crash
        let available = UIImagePickerController.availableMediaTypes(for: .camera) ?? []
        vc.mediaTypes = available.contains("public.movie") ? ["public.movie"] : available
        vc.cameraCaptureMode = .video
        vc.videoQuality = .typeMedium
        vc.allowsEditing = false
        vc.delegate = context.coordinator
        return vc
    }

    func updateUIViewController(_ vc: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onComplete) }

    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let onComplete: (URL?) -> Void
        init(_ onComplete: @escaping (URL?) -> Void) { self.onComplete = onComplete }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            picker.dismiss(animated: true)
            onComplete(info[.mediaURL] as? URL)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
            onComplete(nil)
        }
    }
}

/// 系统照片库视频选择器（PHPickerViewController）。
/// 用户从相册里选一段视频；要新录像可去系统相机 App 录后再回来选。
struct VideoPicker: UIViewControllerRepresentable {
    let onComplete: (URL?) -> Void

    func makeUIViewController(context: Context) -> PHPickerViewController {
        var config = PHPickerConfiguration(photoLibrary: .shared())
        config.filter = .videos
        config.selectionLimit = 1
        config.preferredAssetRepresentationMode = .current
        let vc = PHPickerViewController(configuration: config)
        vc.delegate = context.coordinator
        return vc
    }

    func updateUIViewController(_ vc: PHPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onComplete) }

    final class Coordinator: NSObject, PHPickerViewControllerDelegate {
        let onComplete: (URL?) -> Void
        init(_ onComplete: @escaping (URL?) -> Void) { self.onComplete = onComplete }

        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            picker.dismiss(animated: true)
            guard let provider = results.first?.itemProvider,
                  provider.hasItemConformingToTypeIdentifier("public.movie") else {
                onComplete(nil); return
            }
            // 拷贝到临时目录，PHPicker 返回的 URL 仅在回调期间有效
            provider.loadFileRepresentation(forTypeIdentifier: "public.movie") { [onComplete] url, _ in
                guard let url else {
                    DispatchQueue.main.async { onComplete(nil) }
                    return
                }
                let dest = FileManager.default.temporaryDirectory
                    .appendingPathComponent("picked-\(UUID().uuidString).\(url.pathExtension.isEmpty ? "mov" : url.pathExtension)")
                do {
                    try? FileManager.default.removeItem(at: dest)
                    try FileManager.default.copyItem(at: url, to: dest)
                    DispatchQueue.main.async { onComplete(dest) }
                } catch {
                    DispatchQueue.main.async { onComplete(nil) }
                }
            }
        }
    }
}
#endif
