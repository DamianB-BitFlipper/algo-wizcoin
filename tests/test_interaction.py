import pytest
import algosdk

from algopytest import (
    AlgoUser,
    asset_balance,
    call_app,
    payment_transaction,
    opt_in_asset,
    close_out_asset,
    group_elem,
    group_transaction,
    suggested_params,    
)

TMPL_AMOUNT = 50_000_000

def opt_in_user(owner, user, wizcoin_asset_id):
    """Opt-in the ``user`` to the ``wizcoin_asset_id`` ASA."""
    opt_in_asset(user, wizcoin_asset_id)
    
    # The test runs here    
    yield user
    
    # Clean up by closing out of WizCoin and sending the remaining balance to `owner`    
    close_out_asset(user, wizcoin_asset_id, owner)

@pytest.fixture()
def user1_in(owner, user1, wizcoin_asset_id):
    """Create a ``user1`` fixture that has already opted in to ``wizcoin_asset_id``."""
    yield from opt_in_user(owner, user1, wizcoin_asset_id)

def test_join_wizcoin_membership(owner, user1_in, wizcoin_asset_id, smart_contract_id):
    smart_contract_user = AlgoUser(algosdk.logic.get_application_address(smart_contract_id))
    
    txn0 = group_elem(call_app)(
        sender=user1_in,
        app_id=smart_contract_id,
        app_args=["join_wizcoin"],
        accounts=[user1_in.address],
        foreign_assets=[wizcoin_asset_id],
    )

    # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction
    params = suggested_params(flat_fee=True, fee=2000)
    txn1 = group_elem(payment_transaction)(
        sender=user1_in,
        receiver=smart_contract_user,
        amount=TMPL_AMOUNT,
        params=params, 
    )
    
    # Send the group transaction with the application call and the membership payment
    group_transaction(txn0, txn1)

    # Verify that indeed we own 1 WizCoin membership token
    assert asset_balance(user1_in, wizcoin_asset_id) == 1
