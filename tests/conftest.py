import algosdk
import pytest
from pytest import fixture
from algopytest import (
    AlgoUser,
    SmartContractAccount,
    MultisigAccount,
    create_app,
    call_app,
    delete_app,
    create_asset,
    destroy_asset,    
    transfer_asset,
    update_asset,
    suggested_params,
    payment_transaction,
    opt_in_asset,
    close_out_asset,
    group_transaction,
    multisig_transaction,
    TxnElemsContext,
)

from wizcoin_smart_contract import wizcoin_membership
from clear_program import clear_program

pytest.TMPL_MAX_WIZCOINS = 400
pytest.TMPL_REGISTRATION_AMOUNT = 50_000_000

@fixture
def wizcoin_asset_id(owner):
    # Create the WizCoin asset
    with create_asset(
        sender=owner,
        manager=owner,
        reserve=owner,
        freeze=owner,
        clawback=owner,
        asset_name="WizCoin",
        total=pytest.TMPL_MAX_WIZCOINS,
        decimals=0,
        unit_name="WizToken",
        default_frozen=False,
    ) as asset_id:
        yield asset_id
    
@fixture
def smart_contract_id(owner, wizcoin_asset_id):
    app_id = create_app(
        owner,
        approval_program=wizcoin_membership(), 
        clear_program=clear_program(),
        global_bytes=1,
        global_ints=1,
        app_args=[wizcoin_asset_id],
        version=6,
    )

    # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction
    params = suggested_params(flat_fee=True, fee=2000)
    smart_contract_account = SmartContractAccount(app_id)
        
    # Raise the minimum balance of the smart contract, in order to even be able to
    # opt-in to the WizCoin ASA. The minimum balance is 200000 microAlgos.
    payment_transaction(
        sender=owner,
        receiver=smart_contract_account,
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
        receiver=smart_contract_account,
        amount=pytest.TMPL_MAX_WIZCOINS,
        asset_id=wizcoin_asset_id,
        #close_assets_to=smart_contract_account, # TODO: This produces an error
    )

    # Make the smart contract the reserve account for the WizCoin asset
    update_asset(
        sender=owner,
        asset_id=wizcoin_asset_id,
        manager=owner,
        reserve=smart_contract_account,
        freeze=owner,
        clawback=owner,
    )
        
    yield app_id

    # Relinquish all of the WizCoins back to the manager, so that that manager can destroy the WizCoin ASA
    call_app(
        sender=owner,
        app_id=app_id,
        app_args=["relinquish_wizcoins"],
        accounts=[smart_contract_account],            
        foreign_assets=[wizcoin_asset_id],
        params=params,
    )

    delete_app(owner, app_id)

def opt_in_user(owner, user, wizcoin_asset_id):
    """Opt-in the ``user`` to the ``wizcoin_asset_id`` ASA."""
    opt_in_asset(user, wizcoin_asset_id)
    
    # The test runs here    
    yield user
    
    # Clean up by closing out of WizCoin and sending the remaining balance to `owner`    
    close_out_asset(user, wizcoin_asset_id, owner)
    
@fixture
def user1_in(owner, user1, wizcoin_asset_id):
    """Create a ``user1`` fixture that has already opted in to ``wizcoin_asset_id``."""
    yield from opt_in_user(owner, user1, wizcoin_asset_id)

@fixture
def user2_in(owner, user2, wizcoin_asset_id):
    """Create a ``user2`` fixture that has already opted in to ``wizcoin_asset_id``."""
    yield from opt_in_user(owner, user2, wizcoin_asset_id)

@fixture
def multisig_account_in(owner, user3, user4, wizcoin_asset_id):
    """Create a multisig account with owners ``user3`` and ``user4`` that is opted in to ``wizcoin_asset_id``."""
    signing_accounts = [user3, user4]
    multisig_account = MultisigAccount(
        version=1,
        threshold=2,
        owner_accounts=[user3, user4],
    )

    # Fund the `multisig_account` from `user3` with 100 Algos
    payment_transaction(
        sender=user3,
        receiver=multisig_account,
        amount=100_000_000,
    )

    # Opt the `multisig_account` into the `wizcoin_asset_id`
    with TxnElemsContext():
        opt_in_txn = opt_in_asset(multisig_account, wizcoin_asset_id)
        
    multisig_transaction(
        multisig_account=multisig_account,
        transaction=opt_in_txn,
        signing_accounts=signing_accounts,
    )

    yield multisig_account

    # Opt the `multisig_account` out of the `wizcoin_asset_id`
    with TxnElemsContext():
        close_out_txn = close_out_asset(multisig_account, wizcoin_asset_id, owner)
    
    multisig_transaction(
        multisig_account=multisig_account,
        transaction=close_out_txn,
        signing_accounts=signing_accounts,
    )

    # Return the remaining balance of `multisig_account` back to `user3`
    with TxnElemsContext():
        payment_txn = payment_transaction(
            sender=multisig_account,
            receiver=user3,
            amount=0,
            close_remainder_to=user3,
        )
    
    multisig_transaction(
        multisig_account=multisig_account,        
        transaction=payment_txn,
        signing_accounts=signing_accounts,
    )
    
@fixture
def smart_contract_account(smart_contract_id):
    """Return an ``SmartContractAccount`` representing the address of the ``smart_contract_id``."""
    return SmartContractAccount(smart_contract_id)
    
def join_member(owner, user_in, smart_contract_account, wizcoin_asset_id, smart_contract_id):
    """Grant the ``user`` membership into WizCoin."""
    # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction    
    params = suggested_params(flat_fee=True, fee=2000)

    with TxnElemsContext():
        txn0 = call_app(
            sender=user_in,
            app_id=smart_contract_id,
            app_args=["join_wizcoin"],
            accounts=[user_in],
            foreign_assets=[wizcoin_asset_id],
        )

        txn1 = payment_transaction(
            sender=user_in,
            receiver=smart_contract_account,
            amount=pytest.TMPL_REGISTRATION_AMOUNT,
            params=params, 
        )
    
    # Send the group transaction with the application call and the membership payment
    group_transaction(txn0, txn1)

    # Return the `user_in` after they have joined WizCoin
    yield user_in

@fixture
def user1_member(owner, user1_in, smart_contract_account, wizcoin_asset_id, smart_contract_id):
    """Create a ``user1_member`` fixture which is already a member of WizCoin."""
    yield from join_member(owner, user1_in, smart_contract_account, wizcoin_asset_id, smart_contract_id)

@fixture
def user2_member(owner, user2_in, smart_contract_account, wizcoin_asset_id, smart_contract_id):
    """Create a ``user2_member`` fixture which is already a member of WizCoin."""
    yield from join_member(owner, user1_in, smart_contract_account, wizcoin_asset_id, smart_contract_id)    

@fixture
def multisig_account_member(owner, multisig_account_in, user3, user4, smart_contract_account, wizcoin_asset_id, smart_contract_id):
    """Create a ``multisig_account_member`` fixture which is already a member of WizCoin."""
    # Twice the minimum fee to also cover the transaction fee of the ASA transfer inner transaction
    params = suggested_params(flat_fee=True, fee=2000)
    signing_accounts = [user3, user4]

    with TxnElemsContext():
        # Create a multisig transaction which calls the application on behalf of the multi-signature account
        txn0 = multisig_transaction(
            multisig_account=multisig_account_in,
            transaction=call_app(
                sender=multisig_account_in,
                app_id=smart_contract_id,
                app_args=["join_wizcoin"],
                accounts=[multisig_account_in],
                foreign_assets=[wizcoin_asset_id],            
            ),
            signing_accounts=signing_accounts,
        )

        # Create a multisig transaction which pays the `smart_contract_account` on behalf of the multi-signature account
        txn1 = multisig_transaction(
            multisig_account=multisig_account_in,
            transaction=payment_transaction(
                sender=multisig_account_in,
                receiver=smart_contract_account,
                amount=pytest.TMPL_REGISTRATION_AMOUNT,
                params=params,
            ),
            signing_accounts=signing_accounts,
        )
    
    # Send the group transaction with the application call and the membership payment
    group_transaction(txn0, txn1)

    # Return the `multisig_account_in` after they have joined WizCoin
    yield multisig_account_in   
