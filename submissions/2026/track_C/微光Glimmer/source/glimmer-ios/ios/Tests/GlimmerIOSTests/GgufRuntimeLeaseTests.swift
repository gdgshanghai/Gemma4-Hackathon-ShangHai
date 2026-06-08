import XCTest
@testable import GlimmerIOS

final class GgufRuntimeLeaseTests: XCTestCase {
    func testAcquireMarksOwnerActive() {
        let ownerID = UUID()
        var lease = GgufRuntimeLease()

        lease.acquire(ownerID)

        XCTAssertEqual(lease.activeOwnerID, ownerID)
        XCTAssertTrue(lease.isActive(ownerID))
    }

    func testStaleOwnerCannotReleaseNewOwner() {
        let oldOwnerID = UUID()
        let newOwnerID = UUID()
        var lease = GgufRuntimeLease()

        lease.acquire(oldOwnerID)
        lease.acquire(newOwnerID)

        XCTAssertFalse(lease.release(ifOwnedBy: oldOwnerID))
        XCTAssertEqual(lease.activeOwnerID, newOwnerID)
        XCTAssertTrue(lease.isActive(newOwnerID))
    }

    func testActiveOwnerCanReleaseRuntime() {
        let ownerID = UUID()
        var lease = GgufRuntimeLease()

        lease.acquire(ownerID)

        XCTAssertTrue(lease.release(ifOwnedBy: ownerID))
        XCTAssertNil(lease.activeOwnerID)
        XCTAssertFalse(lease.isActive(ownerID))
    }
}
