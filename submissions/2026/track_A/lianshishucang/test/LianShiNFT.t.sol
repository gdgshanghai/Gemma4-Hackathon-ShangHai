// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/LianShiNFT.sol";

contract LianShiNFTTest is Test {
    event NFTMinted(uint256 indexed tokenId, address indexed creator, address indexed owner, string uri, uint96 royaltyFee, uint256 createdAt);

    LianShiNFT public nft;
    address public alice = address(0x100);
    address public bob = address(0x200);

    function setUp() public {
        vm.prank(alice);
        nft = new LianShiNFT();
    }

    function test_Mint() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://uri", 500);

        assertEq(tokenId, 1);
        assertEq(nft.ownerOf(tokenId), bob);
        assertEq(nft.creatorOf(tokenId), alice);
        assertEq(nft.tokenURI(tokenId), "ipfs://uri");
    }

    function test_MintRoyalty() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://uri", 500);

        (address recipient, uint256 amount) = nft.royaltyInfo(tokenId, 1 ether);
        assertEq(recipient, alice);
        assertEq(amount, 0.05 ether);
    }

    function test_RevertWhen_RoyaltyExceedsMax() public {
        vm.prank(alice);
        vm.expectRevert("Royalty too high, max 10%");
        nft.mint(bob, "ipfs://uri", 1001);
    }

    function test_RevertWhen_MaxRoyaltyAllowed() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://uri", 1000);

        (address recipient, uint256 amount) = nft.royaltyInfo(tokenId, 1 ether);
        assertEq(recipient, alice);
        assertEq(amount, 0.1 ether);
    }

    function test_MintMultipleTokens() public {
        vm.startPrank(alice);
        uint256 id1 = nft.mint(bob, "ipfs://1", 100);
        uint256 id2 = nft.mint(bob, "ipfs://2", 200);
        uint256 id3 = nft.mint(alice, "ipfs://3", 300);
        vm.stopPrank();

        assertEq(id1, 1);
        assertEq(id2, 2);
        assertEq(id3, 3);

        assertEq(nft.ownerOf(1), bob);
        assertEq(nft.ownerOf(2), bob);
        assertEq(nft.ownerOf(3), alice);
    }

    function test_GetNFTMetadata() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://meta", 750);

        LianShiNFT.NFTMetadata memory meta = nft.getNFTMetadata(tokenId);
        assertEq(meta.tokenId, tokenId);
        assertEq(meta.creator, alice);
        assertEq(meta.uri, "ipfs://meta");
        assertEq(meta.royaltyFee, 750);
        assertEq(meta.createdAt, block.timestamp);
    }

    function test_GetCreatorTokens() public {
        vm.startPrank(alice);
        nft.mint(bob, "ipfs://1", 100);
        nft.mint(bob, "ipfs://2", 200);
        vm.stopPrank();

        vm.prank(bob);
        nft.mint(bob, "ipfs://3", 300);

        uint256[] memory aliceTokens = nft.getCreatorTokens(alice);
        assertEq(aliceTokens.length, 2);
        assertEq(aliceTokens[0], 1);
        assertEq(aliceTokens[1], 2);

        uint256[] memory bobTokens = nft.getCreatorTokens(bob);
        assertEq(bobTokens.length, 1);
        assertEq(bobTokens[0], 3);
    }

    function test_RevertWhen_MintToZeroAddress() public {
        vm.prank(alice);
        vm.expectRevert();
        nft.mint(address(0), "ipfs://uri", 100);
    }

    function test_RevertWhen_QueryNonExistentToken() public {
        vm.expectRevert("Token does not exist");
        nft.creatorOf(999);
    }

    function test_SupportsInterface() public {
        assertTrue(nft.supportsInterface(0x80ac58cd));
        assertTrue(nft.supportsInterface(0x2a55205a));
    }

    function test_EventEmittedOnMint() public {
        vm.expectEmit(true, true, true, true, address(nft));
        emit NFTMinted(1, alice, bob, "ipfs://uri", 500, block.timestamp);
        vm.prank(alice);
        nft.mint(bob, "ipfs://uri", 500);
    }

    function test_DifferentCreatorsCanMint() public {
        vm.prank(alice);
        nft.mint(bob, "ipfs://a", 100);

        vm.prank(bob);
        nft.mint(alice, "ipfs://b", 200);

        assertEq(nft.creatorOf(1), alice);
        assertEq(nft.creatorOf(2), bob);
    }

    function test_OwnerOfTransferredToken() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(alice, "ipfs://uri", 100);

        vm.prank(alice);
        nft.transferFrom(alice, bob, tokenId);

        assertEq(nft.ownerOf(tokenId), bob);
        assertEq(nft.creatorOf(tokenId), alice);
    }

    function test_TokenURI() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://unique-uri", 100);

        string memory uri = nft.tokenURI(tokenId);
        assertEq(uri, "ipfs://unique-uri");
    }

    function test_MintAsDifferentMsgSender() public {
        vm.prank(alice);
        uint256 tokenId = nft.mint(bob, "ipfs://uri", 500);

        (address recipient,) = nft.royaltyInfo(tokenId, 1 ether);
        assertEq(recipient, alice);
    }
}
