params = dict(n_dims=64, n_content_dims=256,
              link_prediction_params=dict(lr=0.001, epochs=20, batch_size=1024, margin=0.0,
                                          gcn_layers=3, ncf_layers=2, conv_depth=2,
                                          ncf_gcn_balance=1.0,
                                          gaussian_noise=0.01, kernel_l2=1e-9,
                                          nsh=0.75, ps_proportion=0.0, ps_threshold=0.05,
                                          ns_proportion=1.0, ns_w2v_proportion=0.25, ns_w2v_exponent=0.75),
              collaborative_params=dict(lr=0.001, epochs=5, margin=0.0,
                                        gcn_layers=2, ncf_layers=2, conv_depth=2,
                                        kernel_l2=1e-9, batch_size=1024,
                                        gaussian_noise=0.01,
                                        nsh=0.75, ps_proportion=0.0, ps_threshold=0.05,
                                        ns_proportion=1.0, ns_w2v_proportion=0.25, ns_w2v_exponent=0.75))
