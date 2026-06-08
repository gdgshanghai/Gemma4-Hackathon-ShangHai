import XCTest
@testable import GlimmerCore

final class AsdGgufPromptsTests: XCTestCase {
    func testSystemPromptKeepsScreeningScopeAndCode9Output() {
        XCTAssertTrue(AsdGgufPrompts.system.contains("不是医学诊断"))
        XCTAssertTrue(AsdGgufPrompts.system.contains("不要输出 B10"))
        XCTAssertTrue(AsdGgufPrompts.system.contains("9 位二进制标签码"))
    }

    func testUserPromptKeepsStrictCode9Protocol() {
        XCTAssertTrue(AsdGgufPrompts.userInstruction.contains("^[01]{9}$"))
        XCTAssertTrue(AsdGgufPrompts.userInstruction.contains("不要输出 JSON"))
        XCTAssertTrue(AsdGgufPrompts.userInstruction.contains("完整回答必须正好是 9 个字符"))
    }
}
