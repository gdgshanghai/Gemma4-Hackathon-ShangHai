// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/common/ERC2981.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

interface ILianShiNFTForAuction {
    function creatorOf(uint256 tokenId) external view returns (address);
    function royaltyInfo(uint256 tokenId, uint256 salePrice) external view returns (address, uint256);
}

contract LianShiAuction is ReentrancyGuard, Ownable {
    enum AuctionStatus { Pending, Active, Ended, Cancelled, Settled }

    struct Auction {
        uint256 auctionId;
        uint256 tokenId;
        address nftContract;
        address seller;
        uint256 startPrice;
        uint256 reservePrice;
        uint256 highestBid;
        address highestBidder;
        uint256 startTime;
        uint256 endTime;
        uint256 minBidIncrement;
        AuctionStatus status;
        bool royaltyPaid;
    }

    struct Bid {
        address bidder;
        uint256 amount;
        uint256 timestamp;
    }

    address public platformFeeRecipient;
    uint256 public platformFeeBps;
    uint256 public bidIncrementBps;

    uint256 private _auctionIds;

    mapping(uint256 => Auction) private _auctions;
    mapping(uint256 => Bid[]) private _auctionBids;
    mapping(uint256 => mapping(address => uint256)) private _refundAmounts;

    event AuctionCreated(
        uint256 indexed auctionId,
        uint256 indexed tokenId,
        address indexed nftContract,
        address seller,
        uint256 startPrice,
        uint256 reservePrice,
        uint256 startTime,
        uint256 endTime
    );

    event BidPlaced(
        uint256 indexed auctionId,
        address indexed bidder,
        uint256 amount
    );

    event AuctionEnded(
        uint256 indexed auctionId,
        address winner,
        uint256 winningBid
    );

    event AuctionCancelled(uint256 indexed auctionId);

    event AuctionSettled(
        uint256 indexed auctionId,
        address seller,
        address winner,
        uint256 finalPrice,
        uint256 platformFee,
        uint256 creatorRoyalty
    );

    event RefundClaimed(address indexed bidder, uint256 amount);

    constructor(address _feeRecipient, uint256 _feeBps, uint256 _bidIncrementBps) Ownable() {
        require(_feeBps <= 10000, "Fee too high");
        require(_bidIncrementBps <= 5000, "Increment too high");
        platformFeeRecipient = _feeRecipient;
        platformFeeBps = _feeBps;
        bidIncrementBps = _bidIncrementBps;
    }

    function createAuction(
        address nftContract,
        uint256 tokenId,
        uint256 startPrice,
        uint256 reservePrice,
        uint256 startTime,
        uint256 endTime
    ) external nonReentrant returns (uint256) {
        require(startPrice > 0, "Start price must be > 0");
        require(reservePrice >= startPrice, "Reserve must be >= start price");
        require(endTime > startTime, "End time must be after start time");
        require(endTime > block.timestamp, "End time must be in future");

        IERC721 nft = IERC721(nftContract);
        require(nft.ownerOf(tokenId) == msg.sender, "Not the owner");
        require(
            nft.getApproved(tokenId) == address(this) ||
            nft.isApprovedForAll(msg.sender, address(this)),
            "Auction contract not approved"
        );

        _auctionIds++;
        uint256 auctionId = _auctionIds;

        _auctions[auctionId] = Auction({
            auctionId: auctionId,
            tokenId: tokenId,
            nftContract: nftContract,
            seller: msg.sender,
            startPrice: startPrice,
            reservePrice: reservePrice,
            highestBid: 0,
            highestBidder: address(0),
            startTime: startTime,
            endTime: endTime,
            minBidIncrement: bidIncrementBps,
            status: AuctionStatus.Pending,
            royaltyPaid: false
        });

        emit AuctionCreated(auctionId, tokenId, nftContract, msg.sender, startPrice, reservePrice, startTime, endTime);
        return auctionId;
    }

    function placeBid(uint256 auctionId) external payable nonReentrant {
        Auction storage auction = _auctions[auctionId];

        require(auction.status == AuctionStatus.Pending || auction.status == AuctionStatus.Active, "Auction not active");
        require(block.timestamp >= auction.startTime, "Auction not started");
        require(block.timestamp < auction.endTime, "Auction ended");
        require(msg.sender != auction.seller, "Seller cannot bid");

        if (auction.status == AuctionStatus.Pending) {
            auction.status = AuctionStatus.Active;
        }

        uint256 minBid;
        if (auction.highestBidder == address(0)) {
            minBid = auction.startPrice;
        } else {
            minBid = auction.highestBid + (auction.highestBid * auction.minBidIncrement) / 10000;
        }

        require(msg.value >= minBid, "Bid too low");
        require(msg.value > auction.highestBid, "Bid must be higher than current");

        if (auction.highestBidder != address(0)) {
            _refundAmounts[auctionId][auction.highestBidder] += auction.highestBid;
        }

        auction.highestBid = msg.value;
        auction.highestBidder = msg.sender;

        _auctionBids[auctionId].push(Bid({
            bidder: msg.sender,
            amount: msg.value,
            timestamp: block.timestamp
        }));

        emit BidPlaced(auctionId, msg.sender, msg.value);
    }

    function endAuction(uint256 auctionId) external nonReentrant {
        Auction storage auction = _auctions[auctionId];
        require(auction.status == AuctionStatus.Pending || auction.status == AuctionStatus.Active, "Auction not active");
        require(
            block.timestamp >= auction.endTime ||
            (auction.status == AuctionStatus.Active && auction.highestBidder == address(0) && block.timestamp >= auction.startTime + 7 days),
            "Auction not ended"
        );

        auction.status = AuctionStatus.Ended;

        emit AuctionEnded(auctionId, auction.highestBidder, auction.highestBid);
    }

    function cancelAuction(uint256 auctionId) external nonReentrant {
        Auction storage auction = _auctions[auctionId];
        require(auction.seller == msg.sender, "Not seller");
        require(auction.status == AuctionStatus.Pending || auction.status == AuctionStatus.Active, "Cannot cancel");
        require(auction.highestBidder == address(0), "Has active bids, cannot cancel");

        auction.status = AuctionStatus.Cancelled;

        emit AuctionCancelled(auctionId);
    }

    function settleAuction(uint256 auctionId) external nonReentrant {
        Auction storage auction = _auctions[auctionId];
        require(auction.status == AuctionStatus.Ended, "Auction not ended");
        require(auction.highestBidder != address(0), "No bids placed");

        auction.status = AuctionStatus.Settled;

        address seller = auction.seller;
        address winner = auction.highestBidder;
        uint256 finalPrice = auction.highestBid;
        address nftContract = auction.nftContract;
        uint256 tokenId = auction.tokenId;

        uint256 platformFee = (finalPrice * platformFeeBps) / 10000;
        uint256 creatorRoyalty = 0;
        address creator = address(0);

        try ILianShiNFTForAuction(nftContract).creatorOf(tokenId) returns (address _creator) {
            creator = _creator;
        } catch {
            creator = address(0);
        }

        if (creator != address(0) && creator != seller) {
            (address royaltyRecipient, uint256 royaltyAmount) = ILianShiNFTForAuction(nftContract).royaltyInfo(tokenId, finalPrice);
            if (royaltyRecipient != address(0) && royaltyAmount > 0) {
                creatorRoyalty = royaltyAmount;
                payable(royaltyRecipient).transfer(creatorRoyalty);
            }
        }

        uint256 sellerAmount = finalPrice - platformFee - creatorRoyalty;

        if (platformFee > 0) {
            payable(platformFeeRecipient).transfer(platformFee);
        }

        payable(seller).transfer(sellerAmount);

        IERC721(nftContract).safeTransferFrom(seller, winner, tokenId);

        emit AuctionSettled(auctionId, seller, winner, finalPrice, platformFee, creatorRoyalty);
    }

    function claimRefund(uint256 auctionId) external nonReentrant {
        uint256 refund = _refundAmounts[auctionId][msg.sender];
        require(refund > 0, "No refund available");

        _refundAmounts[auctionId][msg.sender] = 0;

        payable(msg.sender).transfer(refund);

        emit RefundClaimed(msg.sender, refund);
    }

    function getAuction(uint256 auctionId) external view returns (Auction memory) {
        return _auctions[auctionId];
    }

    function getAuctionBids(uint256 auctionId) external view returns (Bid[] memory) {
        return _auctionBids[auctionId];
    }

    function getRefundAmount(uint256 auctionId, address bidder) external view returns (uint256) {
        return _refundAmounts[auctionId][bidder];
    }

    function updatePlatformFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 10000, "Fee too high");
        platformFeeBps = newFeeBps;
    }

    function updateFeeRecipient(address newRecipient) external onlyOwner {
        require(newRecipient != address(0), "Invalid address");
        platformFeeRecipient = newRecipient;
    }

    function updateBidIncrement(uint256 newIncrementBps) external onlyOwner {
        require(newIncrementBps <= 5000, "Increment too high");
        bidIncrementBps = newIncrementBps;
    }
}
