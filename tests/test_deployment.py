import pytest
import algosdk

from algopytest import (
    application_global_state,    
    create_asset,
)

def test_initialization(owner, wizcoin_asset_id, smart_contract_id):
    # Make sure the manager and asset-id were correctly recorded
    state = application_global_state(
        smart_contract_id,
        address_fields=['manager'],
    )

    assert state['ASA_id'] == wizcoin_asset_id
    assert state['manager'] == owner.address
