import pytest
import algosdk

from algopytest import (
    asset_balance,
    asset_info,
    transfer_asset,
    freeze_asset,
    update_asset,
)

def test_join_wizcoin_membership(user1_member, wizcoin_asset_id):
    # Verify that indeed we own 1 WizCoin membership token
    assert asset_balance(user1_member, wizcoin_asset_id) == 1

# TODO: Parameterize over the fixtures
def test_join_wizcoin_multisig_membership(multisig_account_member, wizcoin_asset_id):
    # Verify that indeed we own 1 WizCoin membership token
    assert asset_balance(multisig_account_member, wizcoin_asset_id) == 1
    
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

def test_clawback_wizcoin_membership(owner, user1_member, smart_contract_user, wizcoin_asset_id):
    # Clawback the membership token from `user1_member`
    transfer_asset(
        sender=owner,
        receiver=smart_contract_user,
        revocation_target=user1_member,
        amount=1,
        asset_id=wizcoin_asset_id,
    )

    # Verify that the `user1_member` no longer has their membership token
    assert asset_balance(user1_member, wizcoin_asset_id) == 0
    
def test_relinquish_wizcoin_freeze_clawback(owner, user1_member, smart_contract_user, wizcoin_asset_id):
    # Forever relinquish the ability to freeze or clawback WizCoin membership tokens
    update_asset(
        sender=owner,
        asset_id=wizcoin_asset_id,
        manager=owner,
        reserve=smart_contract_user,
        freeze=None,
        clawback=None,
    )

    # Assert that all of the freeze and clawback addresses have been annulled
    wizcoin_info = asset_info(wizcoin_asset_id)

    assert wizcoin_info['asset']['params']['manager'] == owner.address
    assert wizcoin_info['asset']['params']['reserve'] == smart_contract_user.address
    assert wizcoin_info['asset']['params']['freeze'] == algosdk.constants.ZERO_ADDRESS
    assert wizcoin_info['asset']['params']['clawback'] == algosdk.constants.ZERO_ADDRESS

    
