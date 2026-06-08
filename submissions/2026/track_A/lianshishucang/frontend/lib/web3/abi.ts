export const NFT_ABI = [
  {
    name: 'mint',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'uri', type: 'string' },
      { name: 'royaltyFee', type: 'uint96' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'NFTMinted',
    type: 'event',
    inputs: [
      { name: 'tokenId', type: 'uint256', indexed: true },
      { name: 'creator', type: 'address', indexed: true },
      { name: 'owner', type: 'address', indexed: true },
      { name: 'uri', type: 'string', indexed: false },
      { name: 'royaltyFee', type: 'uint96', indexed: false },
      { name: 'createdAt', type: 'uint256', indexed: false },
    ],
  },
  {
    name: 'tokenURI',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [{ name: '', type: 'string' }],
  },
  {
    name: 'ownerOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [{ name: '', type: 'address' }],
  },
  {
    name: 'creatorOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [{ name: '', type: 'address' }],
  },
];

export const MARKETPLACE_ABI = [
  {
    name: 'createListing',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'nftContract', type: 'address' },
      { name: 'tokenId', type: 'uint256' },
      { name: 'price', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'cancelListing',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [{ name: 'listingId', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'buyItem',
    type: 'function',
    stateMutability: 'payable',
    inputs: [{ name: 'listingId', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'updatePrice',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'listingId', type: 'uint256' },
      { name: 'newPrice', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'getListing',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'listingId', type: 'uint256' }],
    outputs: [
      {
        type: 'tuple',
        components: [
          { name: 'listingId', type: 'uint256' },
          { name: 'tokenId', type: 'uint256' },
          { name: 'nftContract', type: 'address' },
          { name: 'seller', type: 'address' },
          { name: 'price', type: 'uint256' },
          { name: 'active', type: 'bool' },
          { name: 'createdAt', type: 'uint256' },
        ],
      },
    ],
  },
  {
    name: 'getListingByToken',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [
      {
        type: 'tuple',
        components: [
          { name: 'listingId', type: 'uint256' },
          { name: 'tokenId', type: 'uint256' },
          { name: 'nftContract', type: 'address' },
          { name: 'seller', type: 'address' },
          { name: 'price', type: 'uint256' },
          { name: 'active', type: 'bool' },
          { name: 'createdAt', type: 'uint256' },
        ],
      },
    ],
  },
  {
    name: 'createOffer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'nftContract', type: 'address' },
      { name: 'tokenId', type: 'uint256' },
      { name: 'price', type: 'uint256' },
      { name: 'expiration', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'cancelOffer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'tokenId', type: 'uint256' },
      { name: 'offerIndex', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'acceptOffer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'nftContract', type: 'address' },
      { name: 'tokenId', type: 'uint256' },
      { name: 'offerIndex', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'getOffers',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [
      {
        type: 'tuple[]',
        components: [
          { name: 'offerId', type: 'uint256' },
          { name: 'tokenId', type: 'uint256' },
          { name: 'nftContract', type: 'address' },
          { name: 'bidder', type: 'address' },
          { name: 'price', type: 'uint256' },
          { name: 'expiration', type: 'uint256' },
          { name: 'active', type: 'bool' },
          { name: 'createdAt', type: 'uint256' },
        ],
      },
    ],
  },
];

export const ERC721_ABI = [
  {
    name: 'approve',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'tokenId', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'setApprovalForAll',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'operator', type: 'address' },
      { name: 'approved', type: 'bool' },
    ],
    outputs: [],
  },
  {
    name: 'getApproved',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [{ name: '', type: 'address' }],
  },
  {
    name: 'isApprovedForAll',
    type: 'function',
    stateMutability: 'view',
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'operator', type: 'address' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'ownerOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'tokenId', type: 'uint256' }],
    outputs: [{ name: '', type: 'address' }],
  },
];
