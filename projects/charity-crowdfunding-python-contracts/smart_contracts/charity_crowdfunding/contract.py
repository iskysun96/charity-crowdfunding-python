# from algopy import (
#     ARC4Contract,
#     UInt64,
#     Bytes,
#     Global,
#     LocalState,
#     arc4,
#     subroutine,
#     Txn,
#     CreateInnerTransaction,
#     PaymentTransaction,
#     TransactionType,
#     AssetHoldingGet,
#     app_opted_in,
#     InnerTransaction,
# )
from algopy.arc4 import abimethod, baremethod
from algopy import *


class CharityCrowdfunding(ARC4Contract):
    def __init__(self) -> None:
        self.goal = UInt64()
        self.detail = String()
        self.title = String()
        self.fund_raised = UInt64()
        self.donator_num = UInt64()
        self.min_donation = UInt64()
        self.active = UInt64()
        self.reward_nft_id = UInt64()
        self.donator_info = LocalState(UInt64)

    @subroutine
    def _authorize_creator(self) -> None:
        assert Global.creator_address == Txn.sender

    @subroutine
    def _opt_in_asset(self, asset_id: UInt64) -> None:
        self._authorize_creator()

        itxn.AssetTransfer(
            xfer_asset=asset_id,
            asset_receiver=Global.current_application_address,
            fee=0,
        ).submit()

    @abimethod()
    def bootstrap(
        self,
        goal: UInt64,
        detail: String,
        title: String,
        min_donation: UInt64,
        asset_name: String,
        unit_name: String,
        nft_amount: UInt64,
        asset_url: String,
        mbr_pay: gtxn.PaymentTransaction,
    ) -> UInt64:
        self._authorize_creator()

        assert mbr_pay.amount >= Global.min_balance
        assert mbr_pay.receiver == Global.current_application_address
        assert mbr_pay.sender == Global.creator_address

        self.goal = goal
        self.detail = detail
        self.title = title
        self.min_donation = min_donation
        self.fund_raised = UInt64(0)
        self.active = UInt64(1)

        result = itxn.AssetConfig(
            total=nft_amount,
            unit_name=unit_name,
            asset_name=asset_name,
            decimals=0,
            url=asset_url,
            fee=0,
        ).submit()

        self.reward_nft_id = result.created_asset.id
        return self.reward_nft_id

    @baremethod(allow_actions=["OptIn"])
    def opt_in_to_app(self) -> None:
        self.donator_info[Txn.sender] = UInt64(0)

    @abimethod
    def fund(self, fund_pay: gtxn.PaymentTransaction) -> None:
        fund_amount = fund_pay.amount

        assert Txn.sender.is_opted_in(Global.current_application_id)
        assert self.active == 1
        assert fund_amount >= self.min_donation
        assert fund_pay.receiver == Global.current_application_address
        assert fund_pay.sender == Txn.sender

        new_donation_amount = self.donator_info[Txn.sender] + fund_amount
        self.donator_info[Txn.sender] = new_donation_amount
        self.donator_num += 1
        self.fund_raised += fund_amount

        asset_holding = op.AssetHoldingGet.asset_balance(Txn.sender, self.reward_nft_id)

        if asset_holding[1]:
            asa_balance = asset_holding[0]
            if asa_balance == 0:
                itxn.AssetTransfer(
                    xfer_asset=self.reward_nft_id,
                    asset_receiver=Txn.sender,
                    asset_amount=1,
                    fee=0,
                ).submit()

    @abimethod
    def claim_fund(self) -> UInt64:
        self._authorize_creator()

        fund_raised = self.fund_raised

        itxn.Payment(
            receiver=Txn.sender,
            amount=fund_raised,
            fee=0,
        ).submit()

        self.active = UInt64(0)
        self.fund_raised = UInt64(0)
        return self.fund_raised

    @baremethod(allow_actions=["DeleteApplication"])
    def delete_application(self) -> None:
        self._authorize_creator()

        assert self.active == 0
        assert self.fund_raised == 0
