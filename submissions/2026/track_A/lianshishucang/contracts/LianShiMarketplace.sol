// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/common/ERC2981.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

interface ILianShiNFT {
    function creatorOf(uint256 tokenId) external view returns (address);
    function royaltyInfo(uint256 tokenId, uint256 salePrice) external view returns (address, uint256);
}

contract LianShiMarketplace is ReentrancyGuard, Ownable {
    struct Listing {
        uint256 listingId;
        uint256 tokenId;
        address nftContract;
        address seller;
        uint256 price;
        bool active;
        uint256 createdAt;
    }

    struct Offer {
        uint256 offerId;
        uint256 tokenId;
        address nftContract;
        address bidder;
        uint256 price;
        uint256 expiration;
        bool active;
        uint256 createdAt;
    }

    address public platformFeeRecipient;
    uint256 public platformFeeBps;

    uint256 private _listingIds;
    uint256 private _offerIds;

    mapping(uint256 => Listing) private _listings;
    mapping(uint256 => uint256) private _tokenToListing;
    mapping(uint256 => Offer[]) private _tokenOffers;

    event ListingCreated(
        uint256 indexed listingId,
        uint256 indexed tokenId,
        address indexed nftContract,
        address seller,
        uint256 price
    );

    event ListingCancelled(uint256 indexed listingId);
    event PriceUpdated(uint256 indexed listingId, uint256 newPrice);

    event ItemSold(
        uint256 indexed listingId,
        uint256 indexed tokenId,
        address indexed nftContract,
        address seller,
        address buyer,
        uint256 price,
        uint256 platformFee,
        uint256 creatorRoyalty
    );

    event OfferCreated(
        uint256 indexed offerId,
        uint256 indexed tokenId,
        address indexed nftContract,
        address bidder,
        uint256 price,
        uint256 expiration
    );

    event OfferCancelled(uint256 indexed offerId);
    event OfferAccepted(
        uint256 indexed offerId,
        uint256 indexed tokenId,
        address indexed nftContract,
        address seller,
        address bidder,
        uint256 price
    );

    constructor(address _feeRecipient, uint256 _feeBps) Ownable() {
        require(_feeBps <= 10000, "Fee too high");
        platformFeeRecipient = _feeRecipient;
        platformFeeBps = _feeBps;
    }

    function createListing(
        address nftContract,
        uint256 tokenId,
        uint256 price
    ) external nonReentrant returns (uint256) {
        require(price > 0, "Price must be > 0");
        IERC721 nft = IERC721(nftContract);
        require(
            nft.ownerOf(tokenId) == msg.sender,
            "Not the owner"
        );
        require(
            nft.getApproved(tokenId) == address(this) ||
            nft.isApprovedForAll(msg.sender, address(this)),
            "Marketplace not approved"
        );
        require(_tokenToListing[tokenId] == 0 || !_listings[_tokenToListing[tokenId]].active, "Already listed");

        _listingIds++;
        uint256 listingId = _listingIds;

        _listings[listingId] = Listing({
            listingId: listingId,
            tokenId: tokenId,
            nftContract: nftContract,
            seller: msg.sender,
            price: price,
            active: true,
            createdAt: block.timestamp
        });

        _tokenToListing[tokenId] = listingId;

        emit ListingCreated(listingId, tokenId, nftContract, msg.sender, price);
        return listingId;
    }

    function cancelListing(uint256 listingId) external nonReentrant {
        Listing storage listing = _listings[listingId];
        require(listing.active, "Listing not active");
        require(listing.seller == msg.sender, "Not seller");

        listing.active = false;
        _tokenToListing[listing.tokenId] = 0;

        emit ListingCancelled(listingId);
    }

    function updatePrice(uint256 listingId, uint256 newPrice) external nonReentrant {
        require(newPrice > 0, "Price must be > 0");
        Listing storage listing = _listings[listingId];
        require(listing.active, "Listing not active");
        require(listing.seller == msg.sender, "Not seller");

        listing.price = newPrice;

        emit PriceUpdated(listingId, newPrice);
    }

    function buyItem(uint256 listingId) external payable nonReentrant {
        Listing storage listing = _listings[listingId];
        require(listing.active, "Listing not active");
        require(msg.value >= listing.price, "Insufficient payment");
        require(msg.sender != listing.seller, "Seller cannot buy own item");

        listing.active = false;
        _tokenToListing[listing.tokenId] = 0;

        address seller = listing.seller;
        uint256 price = listing.price;
        address nftContract = listing.nftContract;
        uint256 tokenId = listing.tokenId;

        uint256 platformFee = (price * platformFeeBps) / 10000;
        uint256 creatorRoyalty = 0;
        address creator = address(0);

        try ILianShiNFT(nftContract).creatorOf(tokenId) returns (address _creator) {
            creator = _creator;
        } catch {
            creator = address(0);
        }

        if (creator != address(0) && creator != seller) {
            (address royaltyRecipient, uint256 royaltyAmount) = ILianShiNFT(nftContract).royaltyInfo(tokenId, price);
            if (royaltyRecipient != address(0) && royaltyAmount > 0) {
                creatorRoyalty = royaltyAmount;
                payable(royaltyRecipient).transfer(creatorRoyalty);
            }
        }

        uint256 sellerAmount = price - platformFee - creatorRoyalty;

        if (platformFee > 0) {
            payable(platformFeeRecipient).transfer(platformFee);
        }

        payable(seller).transfer(sellerAmount);

        IERC721(nftContract).safeTransferFrom(seller, msg.sender, tokenId);

        emit ItemSold(listingId, tokenId, nftContract, seller, msg.sender, price, platformFee, creatorRoyalty);

        if (msg.value > price) {
            payable(msg.sender).transfer(msg.value - price);
        }
    }

    function createOffer(
        address nftContract,
        uint256 tokenId,
        uint256 price,
        uint256 expiration
    ) external nonReentrant returns (uint256) {
        require(price > 0, "Price must be > 0");
        require(expiration > block.timestamp, "Expiration must be in future");
        IERC721 nft = IERC721(nftContract);
        require(nft.ownerOf(tokenId) != msg.sender, "Owner cannot bid");

        _offerIds++;
        uint256 offerId = _offerIds;

        _tokenOffers[tokenId].push(Offer({
            offerId: offerId,
            tokenId: tokenId,
            nftContract: nftContract,
            bidder: msg.sender,
            price: price,
            expiration: expiration,
            active: true,
            createdAt: block.timestamp
        }));

        emit OfferCreated(offerId, tokenId, nftContract, msg.sender, price, expiration);
        return offerId;
    }

    function cancelOffer(uint256 tokenId, uint256 offerIndex) external nonReentrant {
        Offer storage offer = _tokenOffers[tokenId][offerIndex];
        require(offer.active, "Offer not active");
        require(offer.bidder == msg.sender, "Not bidder");
        offer.active = false;
        emit OfferCancelled(offer.offerId);
    }

    function acceptOffer(
        address nftContract,
        uint256 tokenId,
        uint256 offerIndex
    ) external nonReentrant {
        IERC721 nft = IERC721(nftContract);
        require(nft.ownerOf(tokenId) == msg.sender, "Not the owner");
        require(
            nft.getApproved(tokenId) == address(this) ||
            nft.isApprovedForAll(msg.sender, address(this)),
            "Marketplace not approved"
        );

        Offer storage offer = _tokenOffers[tokenId][offerIndex];
        require(offer.active, "Offer not active");
        require(block.timestamp <= offer.expiration, "Offer expired");
        require(offer.bidder != msg.sender, "Seller cannot accept own offer");

        offer.active = false;

        address bidder = offer.bidder;
        uint256 price = offer.price;

        if (_tokenToListing[tokenId] != 0) {
            Listing storage listing = _listings[_tokenToListing[tokenId]];
            if (listing.active) {
                listing.active = false;
                _tokenToListing[tokenId] = 0;
            }
        }

        uint256 platformFee = (price * platformFeeBps) / 10000;
        uint256 creatorRoyalty = 0;
        address creator = address(0);

        try ILianShiNFT(nftContract).creatorOf(tokenId) returns (address _creator) {
            creator = _creator;
        } catch {
            creator = address(0);
        }

        if (creator != address(0) && creator != msg.sender) {
            (address royaltyRecipient, uint256 royaltyAmount) = ILianShiNFT(nftContract).royaltyInfo(tokenId, price);
            if (royaltyRecipient != address(0) && royaltyAmount > 0) {
                creatorRoyalty = royaltyAmount;
            }
        }

        uint256 sellerAmount = price - platformFee - creatorRoyalty;

        if (platformFee > 0) {
            payable(platformFeeRecipient).transfer(platformFee);
        }
        if (creatorRoyalty > 0) {
            (address royaltyRecipient,) = ILianShiNFT(nftContract).royaltyInfo(tokenId, price);
            payable(royaltyRecipient).transfer(creatorRoyalty);
        }

        payable(msg.sender).transfer(sellerAmount);

        IERC721(nftContract).safeTransferFrom(msg.sender, bidder, tokenId);

        emit OfferAccepted(offer.offerId, tokenId, nftContract, msg.sender, bidder, price);
    }

    function getListing(uint256 listingId) external view returns (Listing memory) {
        return _listings[listingId];
    }

    function getListingByToken(uint256 tokenId) external view returns (Listing memory) {
        uint256 listingId = _tokenToListing[tokenId];
        if (listingId == 0) {
            return Listing(0, 0, address(0), address(0), 0, false, 0);
        }
        return _listings[listingId];
    }

    function getOffers(uint256 tokenId) external view returns (Offer[] memory) {
        return _tokenOffers[tokenId];
    }

    function updatePlatformFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 10000, "Fee too high");
        platformFeeBps = newFeeBps;
    }

    function updateFeeRecipient(address newRecipient) external onlyOwner {
        require(newRecipient != address(0), "Invalid address");
        platformFeeRecipient = newRecipient;
    }
}
