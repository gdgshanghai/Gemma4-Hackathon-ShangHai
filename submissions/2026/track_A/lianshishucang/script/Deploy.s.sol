// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/LianShiNFT.sol";
import "../contracts/LianShiMarketplace.sol";
import "../contracts/LianShiAuction.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address feeRecipient = vm.envAddress("FEE_RECIPIENT");
        uint256 marketplaceFeeBps = vm.envOr("MARKETPLACE_FEE_BPS", uint256(250));
        uint256 auctionFeeBps = vm.envOr("AUCTION_FEE_BPS", uint256(250));
        uint256 auctionBidIncrementBps = vm.envOr("AUCTION_BID_INCREMENT_BPS", uint256(500));

        vm.startBroadcast(deployerPrivateKey);

        LianShiNFT nft = new LianShiNFT();
        LianShiMarketplace marketplace = new LianShiMarketplace(feeRecipient, marketplaceFeeBps);
        LianShiAuction auction = new LianShiAuction(feeRecipient, auctionFeeBps, auctionBidIncrementBps);

        vm.stopBroadcast();

        console2.log("LianShiNFT deployed to:", address(nft));
        console2.log("LianShiMarketplace deployed to:", address(marketplace));
        console2.log("LianShiAuction deployed to:", address(auction));
    }
}
