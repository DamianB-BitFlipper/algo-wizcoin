import pytest
import algosdk

from algopytest import (
    AlgoUser,
    application_global_state,    
    create_asset,
    asset_balance,
    asset_info,
)

def test_initialization(owner, smart_contract_account, wizcoin_asset_id, smart_contract_id):
    # Make sure the manager and asset-id were correctly recorded
    state = application_global_state(
        smart_contract_id,
        address_fields=['manager'],
    )

    assert state['ASA_id'] == wizcoin_asset_id
    assert state['manager'] == owner.address

    # Assert that all of the various properties are correct
    wizcoin_info = asset_info(wizcoin_asset_id)

    assert wizcoin_info['asset']['params']['manager'] == owner.address
    assert wizcoin_info['asset']['params']['reserve'] == smart_contract_account.address
    assert wizcoin_info['asset']['params']['freeze'] == owner.address
    assert wizcoin_info['asset']['params']['clawback'] == owner.address
    assert wizcoin_info['asset']['params']['total'] == 400

def test_non_opt_in_wizcoin(user1, wizcoin_asset_id):
    # When the `asset_balance` is `None`, that means that the `user1` has not opted-in yet to `wizcoin_asset_id
    assert asset_balance(user1, wizcoin_asset_id) is None

def test_opt_in_wizcoin(user1_in, wizcoin_asset_id):
    # When the `asset_balance` is `0`, that means that the `user1` has opted-in, but is not yet a member
    assert asset_balance(user1_in, wizcoin_asset_id) == 0

def test_multisig_opt_in_wizcoin(multisig_account_in, wizcoin_asset_id):
    # When the `asset_balance` is `0`, that means that the `multisig_account_in` has opted-in, but is not yet a member
    assert asset_balance(multisig_account_in, wizcoin_asset_id) == 0    
