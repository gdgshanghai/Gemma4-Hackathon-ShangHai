// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/LianShiNFT.sol";
import "../contracts/LianShiAuction.sol";

contract LianShiAuctionTest is Test {
    LianShiNFT public nft;
    LianShiAuction public auction;
    address public alice = address(0x100);
    address public bob = address(0x200);
    address public charlie = address(0x400);
    address public feeRecipient = address(0x300);
    uint256 constant FEE_BPS = 250;
    uint256 constant BID_INCREMENT_BPS = 500;

    function setUp() public {
        vm.prank(alice);
        nft = new LianShiNFT();

        auction = new LianShiAuction(feeRecipient, FEE_BPS, BID_INCREMENT_BPS);

        vm.prank(alice);
        nft.mint(alice, "ipfs://alice-nft", 500);
    }

    // ── Create ──

    function test_CreateAuction() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        assertEq(auctionId, 1);

        LianShiAuction.Auction memory a = auction.getAuction(auctionId);
        assertEq(a.tokenId, 1);
        assertEq(a.seller, alice);
        assertEq(a.startPrice, 1 ether);
        assertEq(a.reservePrice, 5 ether);
        assertEq(uint8(a.status), uint8(LianShiAuction.AuctionStatus.Pending));
    }

    function test_RevertWhen_CreateAuctionNotApproved() public {
        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        vm.expectRevert("Auction contract not approved");
        auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);
    }

    function test_RevertWhen_StartPriceZero() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        vm.prank(alice);
        vm.expectRevert("Start price must be > 0");
        auction.createAuction(address(nft), 1, 0, 0, block.timestamp + 1 hours, block.timestamp + 25 hours);
    }

    function test_RevertWhen_ReserveBelowStart() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        vm.prank(alice);
        vm.expectRevert("Reserve must be >= start price");
        auction.createAuction(address(nft), 1, 5 ether, 1 ether, block.timestamp + 1 hours, block.timestamp + 25 hours);
    }

    function test_RevertWhen_EndNotAfterStart() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        vm.prank(alice);
        vm.expectRevert("End time must be after start time");
        auction.createAuction(address(nft), 1, 1 ether, 1 ether, block.timestamp + 24 hours, block.timestamp + 1 hours);
    }

    // ── Bidding ──

    function test_PlaceBid() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        LianShiAuction.Auction memory a = auction.getAuction(auctionId);
        assertEq(uint8(a.status), uint8(LianShiAuction.AuctionStatus.Active));
        assertEq(a.highestBid, 2 ether);
        assertEq(a.highestBidder, bob);

        LianShiAuction.Bid[] memory bids = auction.getAuctionBids(auctionId);
        assertEq(bids.length, 1);
        assertEq(bids[0].bidder, bob);
    }

    function test_RevertWhen_BidTooLow() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 5 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        vm.expectRevert("Bid too low");
        auction.placeBid{value: 1 ether}(auctionId);
    }

    function test_RevertWhen_BidBeforeStart() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        vm.expectRevert("Auction not started");
        auction.placeBid{value: 2 ether}(auctionId);
    }

    function test_RevertWhen_SellerBids() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(alice, 100 ether);
        vm.prank(alice);
        vm.expectRevert("Seller cannot bid");
        auction.placeBid{value: 2 ether}(auctionId);
    }

    function test_MultipleBids() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        vm.deal(charlie, 100 ether);
        vm.prank(charlie);
        auction.placeBid{value: 3 ether}(auctionId);

        LianShiAuction.Auction memory a = auction.getAuction(auctionId);
        assertEq(a.highestBid, 3 ether);
        assertEq(a.highestBidder, charlie);

        assertEq(auction.getRefundAmount(auctionId, bob), 2 ether);
    }

    function test_MinBidIncrement() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        uint256 minNext = 2 ether + (2 ether * BID_INCREMENT_BPS) / 10000;

        vm.deal(charlie, 100 ether);
        vm.prank(charlie);
        vm.expectRevert("Bid too low");
        auction.placeBid{value: minNext - 1}(auctionId);
    }

    // ── End / Cancel ──

    function test_EndAuction() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Ended));
    }

    function test_RevertWhen_EndBeforeTime() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.expectRevert("Auction not ended");
        auction.endAuction(auctionId);
    }

    function test_CancelAuction() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.prank(alice);
        auction.cancelAuction(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Cancelled));
    }

    function test_RevertWhen_CancelWithBids() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        vm.prank(alice);
        vm.expectRevert("Has active bids, cannot cancel");
        auction.cancelAuction(auctionId);
    }

    function test_RevertWhen_NotSellerCancels() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.prank(bob);
        vm.expectRevert("Not seller");
        auction.cancelAuction(auctionId);
    }

    // ── Settle ──

    function test_SettleAuction() public {
        vm.startPrank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://alice-nft", 500);
        nft.transferFrom(alice, bob, tokenId);
        vm.stopPrank();

        vm.prank(bob);
        nft.approve(address(auction), tokenId);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(bob);
        uint256 auctionId = auction.createAuction(address(nft), tokenId, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(charlie, 100 ether);
        vm.prank(charlie);
        auction.placeBid{value: 10 ether}(auctionId);

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        uint256 bobBefore = bob.balance;
        uint256 feeBefore = feeRecipient.balance;

        auction.settleAuction(auctionId);

        assertEq(nft.ownerOf(tokenId), charlie);

        uint256 platformFee = (10 ether * FEE_BPS) / 10000;
        (, uint256 royalty) = nft.royaltyInfo(tokenId, 10 ether);
        uint256 sellerAmount = 10 ether - platformFee - royalty;

        assertEq(feeRecipient.balance - feeBefore, platformFee);
        assertEq(bob.balance - bobBefore, sellerAmount);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Settled));
    }

    function test_RevertWhen_SettleNoBids() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        vm.expectRevert("No bids placed");
        auction.settleAuction(auctionId);
    }

    function test_RevertWhen_SettleNotEnded() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        vm.expectRevert("Auction not ended");
        auction.settleAuction(auctionId);
    }

    function test_NoRoyaltyWhenCreatorIsSeller() public {
        vm.prank(alice);
        uint256 newTokenId = nft.mint(alice, "ipfs://self", 500);

        vm.prank(alice);
        nft.approve(address(auction), newTokenId);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), newTokenId, 1 ether, 1 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 10 ether}(auctionId);

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        uint256 aliceBefore = alice.balance;
        uint256 feeBefore = feeRecipient.balance;

        auction.settleAuction(auctionId);

        uint256 platformFee = (10 ether * FEE_BPS) / 10000;
        assertEq(feeRecipient.balance - feeBefore, platformFee);
        assertEq(alice.balance - aliceBefore, 10 ether - platformFee);
    }

    // ── Status transitions ──

    function test_AuctionStatusTransitions() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Pending));

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Active));

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Ended));

        auction.settleAuction(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Settled));
    }

    // ── Refunds ──

    function test_ClaimRefund() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(startTime + 1);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        auction.placeBid{value: 2 ether}(auctionId);

        uint256 bobBefore = bob.balance;

        vm.deal(charlie, 100 ether);
        vm.prank(charlie);
        auction.placeBid{value: 5 ether}(auctionId);

        assertEq(auction.getRefundAmount(auctionId, bob), 2 ether);

        vm.prank(bob);
        auction.claimRefund(auctionId);

        assertEq(bob.balance - bobBefore, 2 ether);
        assertEq(auction.getRefundAmount(auctionId, bob), 0);
    }

    function test_RevertWhen_ClaimNoRefund() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp + 1 hours;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.prank(bob);
        vm.expectRevert("No refund available");
        auction.claimRefund(auctionId);
    }

    // ── 7-day auto-end ──

    function test_EndsAt7DaysWithNoBids() public {
        vm.prank(alice);
        nft.approve(address(auction), 1);

        uint256 startTime = block.timestamp;
        uint256 endTime = startTime + 24 hours;

        vm.prank(alice);
        uint256 auctionId = auction.createAuction(address(nft), 1, 1 ether, 5 ether, startTime, endTime);

        vm.warp(endTime + 1);

        auction.endAuction(auctionId);

        assertEq(uint8(auction.getAuction(auctionId).status), uint8(LianShiAuction.AuctionStatus.Ended));
    }

    // ── Admin ──

    function test_UpdatePlatformFee() public {
        auction.updatePlatformFee(500);
        assertEq(auction.platformFeeBps(), 500);
    }

    function test_RevertWhen_UpdateFeeTooHigh() public {
        vm.expectRevert("Fee too high");
        auction.updatePlatformFee(10001);
    }

    function test_UpdateFeeRecipient() public {
        address newRecipient = address(0x900);
        auction.updateFeeRecipient(newRecipient);
        assertEq(auction.platformFeeRecipient(), newRecipient);
    }

    function test_UpdateBidIncrement() public {
        auction.updateBidIncrement(1000);
        assertEq(auction.bidIncrementBps(), 1000);
    }

    function test_RevertWhen_IncrementTooHigh() public {
        vm.expectRevert("Increment too high");
        auction.updateBidIncrement(5001);
    }

    function test_RevertWhen_NonOwnerUpdates() public {
        vm.prank(bob);
        vm.expectRevert();
        auction.updatePlatformFee(500);
    }

    function test_ConstructorReverts() public {
        vm.expectRevert("Fee too high");
        new LianShiAuction(feeRecipient, 10001, 500);

        vm.expectRevert("Increment too high");
        new LianShiAuction(feeRecipient, 250, 5001);
    }

    receive() external payable {}
}
