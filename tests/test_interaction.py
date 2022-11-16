import pytest
import algosdk

from algopytest import (
    asset_balance,
    asset_info,
    transfer_asset,
    freeze_asset,
    suggested_params,
    TxnElemsContext,
    call_app,
    payment_transaction,
    group_transaction,
    update_asset,
)

@pytest.mark.parametrize(
    "member_name",
    [
        "user1_member",
        "multisig_account_member",
    ]
)
def test_join_wizcoin_membership(member_name, wizcoin_asset_id, request):
    # Retrieve the respective `member` fixture by name
    member = request.getfixturevalue(member_name)

    # Verify that indeed we own 1 WizCoin membership token
    assert asset_balance(member, wizcoin_asset_id) == 1

@pytest.mark.parametrize(
    "call_app_user_name, payment_user_name, payment_amount",
    [
        # WizCoin over-payment
        ("user1_in", "user1_in", pytest.TMPL_REGISTRATION_AMOUNT + 1),
        # WizCoin under-payment
        ("user1_in", "user1_in", pytest.TMPL_REGISTRATION_AMOUNT - 1),
        # Mismatching users joining WizCoin
        ("user1_in", "user2_in", pytest.TMPL_REGISTRATION_AMOUNT),
        # Already a member of WizCoin
        ("user1_member", "user1_member", pytest.TMPL_REGISTRATION_AMOUNT),
    ]
)    
def test_join_wizcoin_membership_raises(
        call_app_user_name,
        payment_user_name,
        payment_amount,        
        wizcoin_asset_id,
        smart_contract_account,
        smart_contract_id,
        request
):
    """Do not send the required amount of Algos for WizCoin membership."""
    # Retrieve the respective `call_app_user` and `payment_user` fixtures by name
    call_app_user = request.getfixturevalue(call_app_user_name)
    payment_user = request.getfixturevalue(payment_user_name)
    
    # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction    
    params = suggested_params(flat_fee=True, fee=2000)

    with TxnElemsContext():
        txn0 = call_app(
            sender=call_app_user,
            app_id=smart_contract_id,
            app_args=["join_wizcoin"],
            accounts=[call_app_user],
            foreign_assets=[wizcoin_asset_id],
        )

        txn1 = payment_transaction(
            sender=payment_user,
            receiver=smart_contract_account,
            amount=payment_amount,
            params=params,
        )
    
    with pytest.raises(algosdk.error.AlgodHTTPError, match=r'transaction .*: logic eval error: assert failed'):
        # Send the group transaction with the application call and the membership payment
        group_transaction(txn0, txn1)
        
def test_transfer_wizcoin_membership(user1_member, user2_in, wizcoin_asset_id):
    # Transfer the membership token from `user1_member` to `user2_in`
    transfer_asset(
        sender=user1_member,
        receiver=user2_in,
        amount=1,
        asset_id=wizcoin_asset_id,
    )

    # Verify that `user1_member` no longer has a balance whereas `user2_in` does
    assert asset_balance(user1_member, wizcoin_asset_id) == 0
    assert asset_balance(user2_in, wizcoin_asset_id) == 1
    
def test_freeze_wizcoin_membership(owner, user1_member, user2_in, wizcoin_asset_id):
    # Let the `owner` freeze `user1_member`. Then upon an attempted asset transfer, it will fail.
    freeze_asset(
        sender=owner,
        target=user1_member,
        new_freeze_state=True,
        asset_id=wizcoin_asset_id,
    )

    with pytest.raises(algosdk.error.AlgodHTTPError, match=f'.*asset {wizcoin_asset_id} frozen in {user1_member.address}.*'):
        transfer_asset(
            sender=user1_member,
            receiver=user2_in,
            amount=1,
            asset_id=wizcoin_asset_id,
        )

    # Unfreeze the account and re-attempt the transfer, which should succeed
    freeze_asset(
        sender=owner,
        target=user1_member,
        new_freeze_state=False,
        asset_id=wizcoin_asset_id,
    )

    transfer_asset(
        sender=user1_member,
        receiver=user2_in,
        amount=1,
        asset_id=wizcoin_asset_id,
    )
        
    # Verify that `user1_member` no longer has a balance whereas `user2_in` does
    assert asset_balance(user1_member, wizcoin_asset_id) == 0
    assert asset_balance(user2_in, wizcoin_asset_id) == 1

def test_clawback_wizcoin_membership(owner, user1_member, smart_contract_account, wizcoin_asset_id):
    # Clawback the membership token from `user1_member`
    transfer_asset(
        sender=owner,
        receiver=smart_contract_account,
        revocation_target=user1_member,
        amount=1,
        asset_id=wizcoin_asset_id,
    )

    # Verify that the `user1_member` no longer has their membership token
    assert asset_balance(user1_member, wizcoin_asset_id) == 0
    
def test_relinquish_wizcoin_freeze_clawback(owner, user1_member, smart_contract_account, wizcoin_asset_id):
    # Forever relinquish the ability to freeze or clawback WizCoin membership tokens
    update_asset(
        sender=owner,
        asset_id=wizcoin_asset_id,
        manager=owner,
        reserve=smart_contract_account,
        freeze=None,
        clawback=None,
    )

    # Assert that all of the freeze and clawback addresses have been annulled
    wizcoin_info = asset_info(wizcoin_asset_id)

    assert wizcoin_info['asset']['params']['manager'] == owner.address
    assert wizcoin_info['asset']['params']['reserve'] == smart_contract_account.address
    assert wizcoin_info['asset']['params']['freeze'] == algosdk.constants.ZERO_ADDRESS
    assert wizcoin_info['asset']['params']['clawback'] == algosdk.constants.ZERO_ADDRESS
