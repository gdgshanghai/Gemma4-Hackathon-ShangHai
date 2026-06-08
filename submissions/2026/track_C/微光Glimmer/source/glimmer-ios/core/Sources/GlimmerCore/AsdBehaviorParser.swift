import Foundation

public struct AsdBehaviorLabel: Equatable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let englishName: String
    public let isTargetBehavior: Bool

    public init(id: String, name: String, englishName: String, isTargetBehavior: Bool) {
        self.id = id
        self.name = name
        self.englishName = englishName
        self.isTargetBehavior = isTargetBehavior
    }

    public func name(language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return name
        case .en:
            return englishName
        }
    }
}

public struct AsdBehaviorReport: Equatable, Sendable {
    public let labelCode: String
    public let features: [String: Bool]
    public let overall: String

    public var detectedLabels: [AsdBehaviorLabel] {
        AsdBehaviorParser.labels.filter { label in
            label.isTargetBehavior && features[label.id] == true
        }
    }

    public var conclusionTitle: String {
        conclusionTitle(language: .zh)
    }

    public func conclusionTitle(language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return detectedLabels.isEmpty ? "未注意到明显自闭症倾向类型行为" : "注意到 \(detectedLabels.count) 类可关注行为"
        case .en:
            return detectedLabels.isEmpty ? "No clear ASD-related behavior features observed" : "\(detectedLabels.count) behavior features to note"
        }
    }

    public var conclusionText: String {
        conclusionText(language: .zh)
    }

    public func conclusionText(language: GlimmerLanguage) -> String {
        let names = detectedLabels.map { $0.name(language: language) }
        guard !names.isEmpty else {
            switch language {
            case .zh:
                return """
                基于本次上传的视频片段，系统暂未观察到明显的可关注行为特征。

                从当前片段来看，孩子的行为表现未呈现出明显异常信号，家长可以先不必过度焦虑。儿童在不同场景、不同情绪状态下的表现可能会有所变化，建议继续结合日常互动、语言回应、眼神交流和兴趣行为等情况进行观察。

                温馨提示
                本结果仅基于当前视频片段中的可观察行为线索生成，不构成医学诊断，也不能替代专业评估。如后续仍有担心，可继续上传更多日常片段，或咨询发育行为儿科、儿童保健科等专业医生。
                """
            case .en:
                return """
                Based on this uploaded video clip, the system did not observe clear behavior features that need attention.

                In this clip, the child's behavior does not show obvious abnormal signals. There is no need to become overly worried based on this single clip. Children's behavior can vary across settings and emotional states, so it is still useful to keep observing daily interaction, language response, eye contact, and interests over time.

                Note
                This result is generated only from observable behavior cues in the current video clip. It is not a medical diagnosis and cannot replace a professional assessment. If concerns continue, you can upload more everyday clips or consult a developmental-behavioral pediatrician, child health clinician, or other qualified professional.
                """
            }
        }
        let featureList = names.enumerated()
            .map { index, name in String(format: "%02d｜%@", index + 1, name) }
            .joined(separator: "\n")
        switch language {
        case .zh:
            return """
            基于本次上传视频片段，系统识别到以下值得关注的行为特征：

            \(featureList)

            结果说明
            以上结果仅基于本次视频片段中的可观察行为线索生成，用于早期筛查与风险提示参考，不构成医学诊断。如家长持续存在担忧，建议结合儿童日常表现，并咨询发育行为儿科、儿童保健科或相关专业医生。
            """
        case .en:
            return """
            Based on this uploaded video clip, the system identified the following behavior features to note:

            \(featureList)

            Result note
            These results are generated only from observable behavior cues in this video clip. They are intended as early screening support and risk-awareness reference, not as a medical diagnosis. If caregivers remain concerned, they should combine this with the child's everyday behavior and consult a developmental-behavioral pediatrician, child health clinician, or another qualified professional.
            """
        }
    }

    public var jsonString: String {
        let featureJSON = AsdBehaviorParser.featureIDs
            .map { id in
                "\"\(id)\":\(features[id] == true ? "true" : "false")"
            }
            .joined(separator: ",")
        return "{\"schema_version\":\"1.0\",\"features\":{\(featureJSON)},\"overall\":\"\(overall)\"}"
    }
}

public enum AsdBehaviorParser {
    public static let featureIDs = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10"]
    public static let labels: [AsdBehaviorLabel] = [
        AsdBehaviorLabel(id: "B01", name: "缺乏或回避眼神接触", englishName: "Absence or avoidance of eye contact", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B02", name: "攻击行为", englishName: "Aggressive behavior", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B03", name: "对感觉输入反应过度或不足", englishName: "Hyper- or hyporeactivity to sensory input", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B04", name: "对言语互动缺乏回应", englishName: "Non-responsiveness to verbal interaction", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B05", name: "非典型语言", englishName: "Non-typical language", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B06", name: "物体排列", englishName: "Object lining-up", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B07", name: "自我击打或自伤行为", englishName: "Self-hitting or self-injurious behavior", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B08", name: "自我旋转或旋转物体", englishName: "Self-spinning or spinning objects", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B09", name: "上肢刻板动作", englishName: "Upper limb stereotypies", isTargetBehavior: true),
        AsdBehaviorLabel(id: "B10", name: "背景（无明显目标行为）", englishName: "Background (no clear target behavior)", isTargetBehavior: false),
    ]

    public static func parse(_ raw: String) -> AsdBehaviorReport? {
        let code = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard code.count == 9, code.allSatisfy({ $0 == "0" || $0 == "1" }) else {
            return nil
        }

        let predictedIDs = Array(featureIDs.prefix(9))
        let chars = Array(code)
        var features: [String: Bool] = [:]
        var anyObserved = false

        for (index, id) in predictedIDs.enumerated() {
            let observed = chars[index] == "1"
            features[id] = observed
            anyObserved = anyObserved || observed
        }

        features["B10"] = !anyObserved
        return AsdBehaviorReport(
            labelCode: code,
            features: features,
            overall: anyObserved ? "behavior_features_observed" : "background"
        )
    }
}
