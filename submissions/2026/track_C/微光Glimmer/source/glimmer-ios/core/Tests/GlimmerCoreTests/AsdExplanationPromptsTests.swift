import XCTest
@testable import GlimmerCore

final class AsdExplanationPromptsTests: XCTestCase {
    func testExplanationSystemKeepsScreeningBoundaryWithoutCodeOnlyConstraint() {
        XCTAssertTrue(AsdExplanationPrompts.system.contains("筛查支持"))
        XCTAssertTrue(AsdExplanationPrompts.system.contains("不是医学结论"))
        XCTAssertTrue(AsdExplanationPrompts.system.contains("视频"))
        XCTAssertTrue(AsdExplanationPrompts.system.contains("音频"))
        XCTAssertFalse(AsdExplanationPrompts.system.contains("只返回 B01 到 B09 的 9 位二进制标签码"))
        XCTAssertFalse(AsdExplanationPrompts.system.contains("诊断"))
        XCTAssertTrue(AsdExplanationPrompts.system(language: .en).contains("screening support"))
        XCTAssertTrue(AsdExplanationPrompts.system(language: .en).contains("not a medical conclusion"))
        XCTAssertFalse(AsdExplanationPrompts.system(language: .en).contains("9-bit binary code"))
    }

    func testExplanationUserPromptDoesNotAskForReclassification() {
        XCTAssertTrue(AsdExplanationPrompts.userInstruction.contains("同一段视频"))
        XCTAssertTrue(AsdExplanationPrompts.userInstruction.contains("不要重新输出 9 位二进制码"))
        XCTAssertTrue(AsdExplanationPrompts.userInstruction.contains("不要重新分类"))
        XCTAssertTrue(AsdExplanationPrompts.userInstruction(language: .en).contains("same video"))
        XCTAssertTrue(AsdExplanationPrompts.userInstruction(language: .en).contains("Do not output the 9-bit binary code again"))
        XCTAssertTrue(AsdExplanationPrompts.userInstruction(language: .en).contains("do not reclassify"))
    }

    func testAssistantResultContextKeepsUserFacingSummaryOnly() throws {
        let report = try XCTUnwrap(AsdBehaviorParser.parse("100000001"))
        let context = AsdExplanationPrompts.assistantResultContext(report: report)

        XCTAssertTrue(context.contains("缺乏或回避眼神接触"))
        XCTAssertTrue(context.contains("上肢刻板动作"))
        XCTAssertFalse(context.contains("9-bit code"))
        XCTAssertFalse(context.contains("B01"))
        XCTAssertFalse(context.contains("B10"))
        XCTAssertFalse(context.contains("true"))
        XCTAssertFalse(context.contains("false"))
        XCTAssertFalse(context.contains("诊断"))

        let englishContext = AsdExplanationPrompts.assistantResultContext(report: report, language: .en)
        XCTAssertTrue(englishContext.contains("Absence or avoidance of eye contact"))
        XCTAssertTrue(englishContext.contains("Upper limb stereotypies"))
        XCTAssertFalse(englishContext.contains("B01"))
        XCTAssertFalse(englishContext.contains("B10"))
        XCTAssertFalse(englishContext.contains("true"))
        XCTAssertFalse(englishContext.contains("false"))
    }
}
