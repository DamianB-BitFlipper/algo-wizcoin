# This example is provided for informational purposes only and has not been audited for security.
import base64
from pyteal import *

tmpl_fee = Int(1000)
tmpl_amount = Int(50_000_000)

var_manager = Bytes("manager")
var_ASA_id = Bytes("ASA_id")

def wizcoin_membership():
    """
    This smart contract issues WizCoin membership ASAs.
    """
    app_call_txn = Gtxn[0]
    pay_in_txn = Gtxn[1]
    
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

    # Checks if the sender of the current transaction invoking this
    # smart contract is the manager
    is_manager = Txn.sender() == App.globalGet(var_manager)

    # Code block invoked when joining WizCoin. This application call is given
    # one argument and one supplied account. The argument is the "join_wizcoin"
    # used by the control flow below. The supplied account (Int(1)) is used
    # to verify that the receiver does not hold any WizCoin token already
    asset_balance = AssetHolding.balance(Int(1), App.globalGet(var_ASA_id))
    join_wizcoin = Seq([
        # Sanity checks
        Assert(Txn.application_args.length() == Int(1)),
        
        # Check that the `pay_in_txn` is the correct amount
        # and is sent to the smart contract
        Assert(pay_in_txn.type_enum() == TxnType.Payment),
        Assert(pay_in_txn.fee() <= tmpl_fee),
        Assert(pay_in_txn.amount() == tmpl_amount),
        Assert(pay_in_txn.receiver() == Global.current_application_address()),

        # Perform some checks before issuing the WizCoin token
        Assert(app_call_txn.accounts[1] == pay_in_txn.sender()),
        Assert(asset_balance == Int(0)),

        # Issue the WizCoin token as an inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.asset_amount: Int(1),
            TxnField.asset_receiver: pay_in_txn.sender()
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
        [Txn.application_args[0] == Bytes("join_wizcoin"), join_wizcoin],
    )

    return program
    
if __name__ == "__main__":
    print(compileTeal(wizcoin_membership(), mode=Mode.Application, version=5))
