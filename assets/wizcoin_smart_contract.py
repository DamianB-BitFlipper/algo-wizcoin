# This example is provided for informational purposes only and has not been audited for security.
import base64
from pyteal import *

tmpl_double_fee = Int(2000)
tmpl_amount = Int(50_000_000)

var_manager = Bytes("manager")
var_ASA_id = Bytes("ASA_id")

def wizcoin_membership():
    """
    This smart contract issues WizCoin membership ASAs.
    """
    # Checks if the sender of the current transaction invoking this
    # smart contract is the manager
    is_manager = Txn.sender() == App.globalGet(var_manager)
    
    # Code block invoked during contract initialization. Saves the
    # the sender (creator) of this smart contract as the manager.
    # This should be the same address as the manager of the WizCoin ASA.
    init_contract = Seq([
        # Sanity checks
        Assert(Txn.application_args.length() == Int(1)),
        
        App.globalPut(var_manager, Txn.sender()),
        App.globalPut(var_ASA_id, Btoi(Txn.application_args[0])),
        Return(Int(1))
    ])

    # Code block invoked in order for the smart contract to opt-in to the WizCoin ASA.
    # This operation must be performed as an inner transaction; the smart
    # contract has no explicit private key to opt in otherwise.
    opt_in_wizcoin = Seq([
        # Sanity checks        
        Assert(is_manager),
        Assert(Txn.application_args.length() == Int(1)),

        # Opt-in to the WizCoin ASA. That is done with a 0 transfer to
        # the smart contract's address
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.asset_amount: Int(0),
            TxnField.xfer_asset: App.globalGet(var_ASA_id),
        }),
        InnerTxnBuilder.Submit(),
        
        Approve(),        
    ])

    # Code block invoked in order to send all of the reserve WizCoin tokens
    # back to the manager so that the manager can destroy the asset.
    # Pass in the smart contract address as an account to get our own WizCoin balance.
    # This operation must be performed as an inner transaction; the smart
    # contract has no explicit private key to opt in otherwise.
    own_asset_balance = AssetHolding.balance(Int(1), App.globalGet(var_ASA_id))
    relinquish_wizcoins = Seq([
        # Sanity checks        
        Assert(is_manager),
        Assert(Txn.application_args.length() == Int(1)),
        Assert(Txn.accounts.length() == Int(1)),
        
        own_asset_balance,
        Assert(own_asset_balance.hasValue()),
        
        # Return the remaining WizCoins back to the manager
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.asset_receiver: App.globalGet(var_manager),
            TxnField.asset_amount: own_asset_balance.value(),
            TxnField.xfer_asset: App.globalGet(var_ASA_id),
        }),
        InnerTxnBuilder.Submit(),
        
        Approve(),        
    ])    

    # Code block invoked when joining WizCoin. This application call is given
    # one argument and one supplied account. The argument is the "join_wizcoin"
    # used by the control flow below. The supplied account (Int(1)) is used
    # to verify that the receiver does not hold any WizCoin token already
    app_call_txn = Gtxn[0]
    pay_in_txn = Gtxn[1]    
    asset_balance = AssetHolding.balance(Int(1), App.globalGet(var_ASA_id))
    join_wizcoin = Seq([
        # Sanity checks
        Assert(Global.group_size() == Int(2)),        
        Assert(Txn.application_args.length() == Int(1)),
        Assert(Txn.accounts.length() == Int(1)),
        
        # Check that the `pay_in_txn` is the correct amount
        # and is sent to the smart contract
        Assert(pay_in_txn.type_enum() == TxnType.Payment),
        Assert(pay_in_txn.fee() >= tmpl_double_fee),
        Assert(pay_in_txn.amount() == tmpl_amount),
        Assert(pay_in_txn.receiver() == Global.current_application_address()),

        # Perform some checks before issuing the WizCoin token
        Assert(app_call_txn.accounts[1] == pay_in_txn.sender()),
        asset_balance,
        Assert(asset_balance.hasValue()),
        Assert(asset_balance.value() == Int(0)),

        # Issue the WizCoin token as an inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: App.globalGet(var_ASA_id),            
            TxnField.asset_receiver: pay_in_txn.sender(),
            TxnField.asset_amount: Int(1),            
        }),
        InnerTxnBuilder.Submit(),
        
        Approve(),
    ])

    # TODO: Add a block where the manager can withdraw the ALGOs sent to this smart contract
    
    # Control flow logic of the smart contract
    program = Cond(
        [Txn.application_id() == Int(0), init_contract],
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(is_manager)],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(is_manager)],
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [Txn.on_completion() == OnComplete.CloseOut, Approve()],
        [Txn.application_args[0] == Bytes("opt_in_wizcoin"), opt_in_wizcoin],        
        [Txn.application_args[0] == Bytes("join_wizcoin"), join_wizcoin],
        [Txn.application_args[0] == Bytes("relinquish_wizcoins"), relinquish_wizcoins],
    )

    return program
    
if __name__ == "__main__":
    print(compileTeal(wizcoin_membership(), mode=Mode.Application, version=5))
