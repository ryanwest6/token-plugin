from plenum.common.constants import DOMAIN_LEDGER_ID, CONFIG_LEDGER_ID, \
    NodeHooks, ReplicaHooks


def integrate_plugin_in_node(node):
    from sovtokenfees.client_authnr import FeesAuthNr
    from sovtokenfees.static_fee_req_handler import StaticFeesReqHandler
    from sovtokenfees.three_phase_commit_handling import \
        ThreePhaseCommitHandler
    from sovtoken import TOKEN_LEDGER_ID
    from sovtoken.client_authnr import TokenAuthNr

    token_authnr = node.clientAuthNr.get_authnr_by_type(TokenAuthNr)
    if not token_authnr:
        raise ImportError('sovtoken plugin should be loaded, ' # noqa
                                  'authenticator not found')
    token_req_handler = node.get_req_handler(ledger_id=TOKEN_LEDGER_ID)
    if not token_req_handler:
        raise ImportError('sovtoken plugin should be loaded, request ' # noqa
                                  'handler not found')

    # `handle_xfer_public_txn` in `TokenReqHandler` checks if the sum of inputs match
    # exactly the sum of outputs. Since the check to match inputs and outputs is done
    # during fees handling the check is avoided in `TokenReqHandler` by monkeypatching
    # `handle_xfer_public_txn` to do nothing.
    token_req_handler.handle_xfer_public_txn = lambda _: None

    token_ledger = token_req_handler.ledger
    token_state = token_req_handler.state
    utxo_cache = token_req_handler.utxo_cache
    fees_authnr = FeesAuthNr(node.getState(DOMAIN_LEDGER_ID), token_authnr)
    fees_req_handler = StaticFeesReqHandler(node.configLedger,
                                            node.getState(CONFIG_LEDGER_ID),
                                            token_ledger,
                                            token_state,
                                            utxo_cache,
                                            node.getState(DOMAIN_LEDGER_ID),
                                            node.bls_bft.bls_store)
    node.clientAuthNr.register_authenticator(fees_authnr)
    node.register_req_handler(fees_req_handler, CONFIG_LEDGER_ID)
    node.register_hook(NodeHooks.PRE_SIG_VERIFICATION, fees_authnr.verify_signature)
    node.register_hook(NodeHooks.PRE_DYNAMIC_VALIDATION, fees_req_handler.can_pay_fees)
    node.register_hook(NodeHooks.POST_REQUEST_APPLICATION, fees_req_handler.deduct_fees)
    node.register_hook(NodeHooks.POST_REQUEST_COMMIT, fees_req_handler.commit_fee_txns)
    node.register_hook(NodeHooks.POST_BATCH_CREATED, fees_req_handler.post_batch_created)
    node.register_hook(NodeHooks.POST_BATCH_REJECTED, fees_req_handler.post_batch_rejected)
    node.register_hook(NodeHooks.POST_BATCH_COMMITTED,
                       fees_req_handler.post_batch_committed)

    three_pc_handler = ThreePhaseCommitHandler(node.master_replica,
                                               token_ledger, token_state,
                                               fees_req_handler)
    node.master_replica.register_hook(ReplicaHooks.CREATE_PPR,
                                      three_pc_handler.add_to_pre_prepare)
    node.master_replica.register_hook(ReplicaHooks.CREATE_PR,
                                      three_pc_handler.add_to_prepare)
    node.master_replica.register_hook(ReplicaHooks.CREATE_ORD,
                                      three_pc_handler.add_to_ordered)
    node.master_replica.register_hook(ReplicaHooks.APPLY_PPR,
                                      three_pc_handler.check_recvd_pre_prepare)

    return node
