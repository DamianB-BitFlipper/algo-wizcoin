import algosdk
from pytest import fixture
from algopytest import (
    AlgoUser,    
    deploy_smart_contract,
    call_app,
    create_asset,
    destroy_asset,    
    transfer_asset,
    update_asset,
    suggested_params,
    payment_transaction,
)

from wizcoin_smart_contract import wizcoin_membership
from clear_program import clear_program

TMPL_MAX_WIZCOINS = 400

@fixture
def wizcoin_asset_id(owner):
    # Create the WizCoin asset
    asset_id = create_asset(
        sender=owner,
        manager=owner,
        reserve=owner,
        freeze=owner,
        clawback=owner,
        asset_name="WizCoin",
        total=TMPL_MAX_WIZCOINS,
        decimals=0,
        unit_name="WizToken",
        default_frozen=False,
    )
    
    yield asset_id

    # Clean up the Wizcoin asset
    destroy_asset(
        sender=owner,
        asset_id=asset_id,
    )

    
@fixture
def smart_contract_id(owner, wizcoin_asset_id):    
    with deploy_smart_contract(
        owner,
        approval_program=wizcoin_membership(), 
        clear_program=clear_program(),
        global_bytes=1,
        global_ints=1,
        app_args=[wizcoin_asset_id],
    ) as app_id:
        # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction
        params = suggested_params(flat_fee=True, fee=2000)
        smart_contract_user = AlgoUser(algosdk.logic.get_application_address(app_id))
        
        # Raise the minimum balance of the smart contract, in order to even be able to
        # opt-in to the WizCoin ASA. The minimum balance is 200000 microAlgos.
        payment_transaction(
            sender=owner,
            receiver=smart_contract_user,
            amount=200000,
        )
        
        # Opt in the smart contract to the WizCoin ASA via an application call. This application
        # call triggers an inner transaction which opts the smart contract in.
        call_app(
            sender=owner,
            app_id=app_id,
            app_args=["opt_in_wizcoin"],
            foreign_assets=[wizcoin_asset_id],
            params=params,
        )
        
        # Transfer all (close out) of the WizCoins to the smart contract
        transfer_asset(
            sender=owner,
            receiver=smart_contract_user,
            amount=TMPL_MAX_WIZCOINS,
            asset_id=wizcoin_asset_id,
            #close_assets_to=smart_contract_user, # TODO: This produces an error
        )

        # Make the smart contract the reserve account for the WizCoin asset
        update_asset(
            sender=owner,
            asset_id=wizcoin_asset_id,
            manager=owner,
            reserve=smart_contract_user,
            freeze=smart_contract_user,
            clawback=smart_contract_user,
        )
        
        yield app_id

        # Relinquish all of the WizCoins back to the manager, so that that user can close the WizCoin ASA
        call_app(
            sender=owner,
            app_id=app_id,
            app_args=["relinquish_wizcoins"],
            accounts=[smart_contract_user.address],            
            foreign_assets=[wizcoin_asset_id],
            params=params,
        )