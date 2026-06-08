// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/common/ERC2981.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract LianShiNFT is ERC721URIStorage, ERC2981, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIds;

    struct NFTMetadata {
        uint256 tokenId;
        address creator;
        string uri;
        uint96 royaltyFee;
        uint256 createdAt;
    }

    mapping(uint256 => NFTMetadata) private _metadata;
    mapping(address => uint256[]) private _creatorTokens;

    event NFTMinted(
        uint256 indexed tokenId,
        address indexed creator,
        address indexed owner,
        string uri,
        uint96 royaltyFee,
        uint256 createdAt
    );

    event RoyaltyUpdated(
        uint256 indexed tokenId,
        address indexed recipient,
        uint96 feeNumerator
    );

    constructor() ERC721("LianShi NFT", "LSNFT") Ownable() {}

    function mint(
        address to,
        string memory uri,
        uint96 royaltyFee
    ) external returns (uint256) {
        require(royaltyFee <= 1000, "Royalty too high, max 10%");

        _tokenIds.increment();
        uint256 newTokenId = _tokenIds.current();

        _safeMint(to, newTokenId);
        _setTokenURI(newTokenId, uri);
        _setTokenRoyalty(newTokenId, msg.sender, royaltyFee);

        _metadata[newTokenId] = NFTMetadata({
            tokenId: newTokenId,
            creator: msg.sender,
            uri: uri,
            royaltyFee: royaltyFee,
            createdAt: block.timestamp
        });

        _creatorTokens[msg.sender].push(newTokenId);

        emit NFTMinted(newTokenId, msg.sender, to, uri, royaltyFee, block.timestamp);

        return newTokenId;
    }

    function creatorOf(uint256 tokenId) external view returns (address) {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        return _metadata[tokenId].creator;
    }

    function getNFTMetadata(uint256 tokenId) external view returns (NFTMetadata memory) {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        return _metadata[tokenId];
    }

    function getCreatorTokens(address creator) external view returns (uint256[] memory) {
        return _creatorTokens[creator];
    }

    function tokenURI(uint256 tokenId) public view override(ERC721URIStorage) returns (string memory) {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721URIStorage, ERC2981) returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}
