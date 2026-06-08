// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/LianShiNFT.sol";
import "../contracts/LianShiMarketplace.sol";

contract LianShiMarketplaceTest is Test {
    LianShiNFT public nft;
    LianShiMarketplace public marketplace;
    address public alice = address(0x100);
    address public bob = address(0x200);
    address public feeRecipient = address(0x300);
    address public charlie = address(0x400);
    uint256 constant FEE_BPS = 250;

    function setUp() public {
        vm.prank(alice);
        nft = new LianShiNFT();

        marketplace = new LianShiMarketplace(feeRecipient, FEE_BPS);

        vm.prank(alice);
        nft.mint(alice, "ipfs://alice-nft", 500);
    }

    // ── Listing ──

    function test_CreateListing() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        assertEq(listingId, 1);

        LianShiMarketplace.Listing memory listing = marketplace.getListing(listingId);
        assertEq(listing.tokenId, 1);
        assertEq(listing.seller, alice);
        assertEq(listing.price, 1 ether);
        assertTrue(listing.active);
    }

    function test_CreateListingWithApprovalForAll() public {
        vm.prank(alice);
        nft.setApprovalForAll(address(marketplace), true);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 2 ether);

        LianShiMarketplace.Listing memory listing = marketplace.getListingByToken(1);
        assertEq(listing.price, 2 ether);
        assertTrue(listing.active);
    }

    function test_RevertWhen_NotOwner() public {
        vm.prank(bob);
        vm.expectRevert("Not the owner");
        marketplace.createListing(address(nft), 1, 1 ether);
    }

    function test_RevertWhen_NotApproved() public {
        vm.prank(alice);
        vm.expectRevert("Marketplace not approved");
        marketplace.createListing(address(nft), 1, 1 ether);
    }

    function test_RevertWhen_PriceZero() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        vm.expectRevert("Price must be > 0");
        marketplace.createListing(address(nft), 1, 0);
    }

    function test_RevertWhen_DoubleList() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(alice);
        vm.expectRevert("Already listed");
        marketplace.createListing(address(nft), 1, 2 ether);
    }

    function test_CancelListing() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(alice);
        marketplace.cancelListing(listingId);

        assertFalse(marketplace.getListing(listingId).active);
        assertEq(marketplace.getListingByToken(1).listingId, 0);
    }

    function test_RevertWhen_CancelNotSeller() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(bob);
        vm.expectRevert("Not seller");
        marketplace.cancelListing(listingId);
    }

    function test_UpdatePrice() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(alice);
        marketplace.updatePrice(listingId, 2 ether);

        assertEq(marketplace.getListing(listingId).price, 2 ether);
    }

    function test_RevertWhen_UpdatePriceNotSeller() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(bob);
        vm.expectRevert("Not seller");
        marketplace.updatePrice(listingId, 2 ether);
    }

    // ── Buy ──

    function test_BuyItem() public {
        vm.startPrank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://alice-nft", 500);
        nft.transferFrom(alice, bob, tokenId);
        vm.stopPrank();

        vm.prank(bob);
        nft.approve(address(marketplace), tokenId);

        vm.prank(bob);
        uint256 listingId = marketplace.createListing(address(nft), tokenId, 10 ether);

        uint256 bobBefore = bob.balance;
        uint256 feeBefore = feeRecipient.balance;

        vm.deal(charlie, 100 ether);
        vm.prank(charlie);
        marketplace.buyItem{value: 10 ether}(listingId);

        assertEq(nft.ownerOf(tokenId), charlie);

        uint256 platformFee = (10 ether * FEE_BPS) / 10000;
        (, uint256 royalty) = nft.royaltyInfo(tokenId, 10 ether);
        uint256 sellerAmount = 10 ether - platformFee - royalty;

        assertEq(feeRecipient.balance - feeBefore, platformFee);
        assertEq(bob.balance - bobBefore, sellerAmount);
    }

    function test_BuyItemWithSurplusRefund() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 5 ether);

        uint256 bobBefore = bob.balance;
        vm.deal(bob, 100 ether);
        vm.prank(bob);
        marketplace.buyItem{value: 10 ether}(listingId);

        assertEq(bob.balance - bobBefore, 100 ether - 5 ether);
        assertEq(nft.ownerOf(1), bob);
    }

    function test_RevertWhen_SellerBuysOwn() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.deal(alice, 100 ether);
        vm.prank(alice);
        vm.expectRevert("Seller cannot buy own item");
        marketplace.buyItem{value: 1 ether}(listingId);
    }

    function test_RevertWhen_BuyInactiveListing() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(alice);
        marketplace.cancelListing(listingId);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        vm.expectRevert("Listing not active");
        marketplace.buyItem{value: 1 ether}(listingId);
    }

    function test_RevertWhen_InsufficientPayment() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 10 ether);

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        vm.expectRevert("Insufficient payment");
        marketplace.buyItem{value: 5 ether}(listingId);
    }

    function test_BuyItemNoRoyaltyWhenCreatorIsSeller() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://self", 500);

        vm.prank(alice);
        nft.approve(address(marketplace), tokenId);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), tokenId, 10 ether);

        uint256 aliceBefore = alice.balance;
        uint256 feeBefore = feeRecipient.balance;

        vm.deal(bob, 100 ether);
        vm.prank(bob);
        marketplace.buyItem{value: 10 ether}(listingId);

        uint256 platformFee = (10 ether * FEE_BPS) / 10000;
        uint256 sellerAmount = 10 ether - platformFee;

        assertEq(alice.balance - aliceBefore, sellerAmount);
        assertEq(feeRecipient.balance - feeBefore, platformFee);
    }

    // ── Offers ──

    function test_CreateOffer() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        uint256 offerId = marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp + 1 days);

        assertEq(offerId, 1);

        LianShiMarketplace.Offer[] memory offers = marketplace.getOffers(1);
        assertEq(offers.length, 1);
        assertEq(offers[0].bidder, bob);
        assertEq(offers[0].price, 8 ether);
        assertTrue(offers[0].active);
    }

    function test_RevertWhen_OwnerCreatesOffer() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(alice);
        vm.expectRevert("Owner cannot bid");
        marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp + 1 days);
    }

    function test_RevertWhen_OfferExpired() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        vm.expectRevert("Expiration must be in future");
        marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp);
    }

    function test_RevertWhen_OfferZeroPrice() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        vm.expectRevert("Price must be > 0");
        marketplace.createOffer(address(nft), 1, 0, block.timestamp + 1 days);
    }

    function test_CancelOffer() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp + 1 days);

        vm.prank(bob);
        marketplace.cancelOffer(1, 0);

        assertFalse(marketplace.getOffers(1)[0].active);
    }

    function test_RevertWhen_CancelOfferNotBidder() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp + 1 days);

        vm.prank(alice);
        vm.expectRevert("Not bidder");
        marketplace.cancelOffer(1, 0);
    }

    function test_AcceptOffer() public {
        vm.startPrank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://alice-nft", 500);
        nft.transferFrom(alice, bob, tokenId);
        vm.stopPrank();

        vm.prank(bob);
        nft.approve(address(marketplace), tokenId);

        vm.prank(bob);
        marketplace.createListing(address(nft), tokenId, 10 ether);

        vm.prank(charlie);
        marketplace.createOffer(address(nft), tokenId, 8 ether, block.timestamp + 1 days);

        vm.deal(address(marketplace), 10 ether);

        uint256 bobBefore = bob.balance;
        uint256 feeBefore = feeRecipient.balance;

        vm.prank(bob);
        marketplace.acceptOffer(address(nft), tokenId, 0);

        assertEq(nft.ownerOf(tokenId), charlie);

        uint256 platformFee = (8 ether * FEE_BPS) / 10000;
        (, uint256 royalty) = nft.royaltyInfo(tokenId, 8 ether);
        uint256 sellerAmount = 8 ether - platformFee - royalty;

        assertEq(feeRecipient.balance - feeBefore, platformFee);
        assertEq(bob.balance - bobBefore, sellerAmount);
    }

    function test_AcceptOfferDeactivatesListing() public {
        vm.startPrank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://alice-nft", 500);
        nft.transferFrom(alice, bob, tokenId);
        vm.stopPrank();

        vm.prank(bob);
        nft.approve(address(marketplace), tokenId);

        vm.prank(bob);
        uint256 listingId = marketplace.createListing(address(nft), tokenId, 10 ether);

        vm.prank(charlie);
        marketplace.createOffer(address(nft), tokenId, 8 ether, block.timestamp + 1 days);

        vm.deal(address(marketplace), 10 ether);

        vm.prank(bob);
        marketplace.acceptOffer(address(nft), tokenId, 0);

        assertFalse(marketplace.getListing(listingId).active);
    }

    function test_RevertWhen_AcceptExpiredOffer() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 10 ether);

        vm.prank(bob);
        marketplace.createOffer(address(nft), 1, 8 ether, block.timestamp + 1 days);

        vm.warp(block.timestamp + 2 days);

        vm.prank(alice);
        vm.expectRevert("Offer expired");
        marketplace.acceptOffer(address(nft), 1, 0);
    }

    function test_RevertWhen_AcceptOfferNotApproved() public {
        vm.prank(charlie);
        uint256 tokenId = nft.mint(charlie, "ipfs://c", 100);

        vm.prank(bob);
        marketplace.createOffer(address(nft), tokenId, 5 ether, block.timestamp + 1 days);

        vm.prank(charlie);
        vm.expectRevert("Marketplace not approved");
        marketplace.acceptOffer(address(nft), tokenId, 0);
    }

    // ── Query ──

    function test_GetListingByToken() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        marketplace.createListing(address(nft), 1, 5 ether);

        LianShiMarketplace.Listing memory listing = marketplace.getListingByToken(1);
        assertEq(listing.price, 5 ether);
        assertTrue(listing.active);
    }

    function test_GetListingByTokenNonExistent() public view {
        LianShiMarketplace.Listing memory listing = marketplace.getListingByToken(999);
        assertEq(listing.listingId, 0);
        assertFalse(listing.active);
    }

    // ── Re-list ──

    function test_RelistAfterCancel() public {
        vm.prank(alice);
        nft.approve(address(marketplace), 1);

        vm.prank(alice);
        uint256 listingId = marketplace.createListing(address(nft), 1, 1 ether);

        vm.prank(alice);
        marketplace.cancelListing(listingId);

        vm.prank(alice);
        uint256 newListingId = marketplace.createListing(address(nft), 1, 2 ether);

        assertEq(newListingId, 2);
        assertTrue(marketplace.getListing(newListingId).active);
    }

    // ── Admin ──

    function test_UpdatePlatformFee() public {
        marketplace.updatePlatformFee(500);
        assertEq(marketplace.platformFeeBps(), 500);
    }

    function test_RevertWhen_UpdateFeeTooHigh() public {
        vm.expectRevert("Fee too high");
        marketplace.updatePlatformFee(10001);
    }

    function test_UpdateFeeRecipient() public {
        address newRecipient = address(0x900);
        marketplace.updateFeeRecipient(newRecipient);
        assertEq(marketplace.platformFeeRecipient(), newRecipient);
    }

    function test_RejectZeroFeeRecipient() public {
        vm.expectRevert("Invalid address");
        marketplace.updateFeeRecipient(address(0));
    }

    function test_RevertWhen_NonOwnerUpdatesFee() public {
        vm.prank(bob);
        vm.expectRevert();
        marketplace.updatePlatformFee(500);
    }

    function test_ConstructorRevertWhenFeeTooHigh() public {
        vm.expectRevert("Fee too high");
        new LianShiMarketplace(feeRecipient, 10001);
    }

    receive() external payable {}
}
