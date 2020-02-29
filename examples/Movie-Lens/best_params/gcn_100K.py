params = {
  1: dict(n_dims=112, combining_factor=0.1,
                           collaborative_params=dict(
                               prediction_network_params=dict(lr=0.05, epochs=100, batch_size=1536,
                                                              network_depth=2,
                                                              gaussian_noise=0.38, conv_depth=1,
                                                              kernel_l2=1e-9, dropout=0.0,),
                               user_item_params=dict(gcn_lr=0.0005, gcn_epochs=25, gcn_layers=3, gcn_dropout=0.0,
                                                     gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                     margin=1.0,
                                                     gaussian_noise=0.05,
                                                     node2vec_params=dict(num_walks=150, q=0.25)))),
  2: dict(n_dims=112, combining_factor=0.1,
                           collaborative_params=dict(
                               prediction_network_params=dict(lr=0.05, epochs=100, batch_size=1536,
                                                              network_depth=3,
                                                              gaussian_noise=0.37, conv_depth=2,
                                                              kernel_l2=1e-9,),
                               user_item_params=dict(gcn_lr=0.0005, gcn_epochs=30, gcn_layers=2,
                                                     gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                     margin=1.0,
                                                     gaussian_noise=0.05,
                                                     node2vec_params=dict(num_walks=200, q=0.25)))),
  3: dict(n_dims=112, combining_factor=0.1,
                  collaborative_params=dict(
                    prediction_network_params=dict(lr=0.03, epochs=75, batch_size=1024,
                                                   network_depth=3,
                                                   gaussian_noise=0.3, conv_depth=2,
                                                   kernel_l2=1e-9, dropout=0.0,),
                    user_item_params=dict(gcn_lr=0.00075, gcn_epochs=20, gcn_layers=2, gcn_dropout=0.0,
                                          gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                          margin=1.0,
                                          gaussian_noise=0.15,
                                          node2vec_params=dict(num_walks=150, q=0.25)))),
  4: dict(n_dims=112, combining_factor=0.1,
                           collaborative_params=dict(
                               prediction_network_params=dict(lr=0.05, epochs=100, batch_size=1536,
                                                              network_depth=3,
                                                              gaussian_noise=0.35, conv_depth=2,
                                                              kernel_l2=1e-9, dropout=0.0,),
                               user_item_params=dict(gcn_lr=0.00075, gcn_epochs=20, gcn_layers=2, gcn_dropout=0.0,
                                                     gcn_kernel_l2=1e-8, gcn_batch_size=1024,
                                                     margin=1.0,
                                                     gaussian_noise=0.15,
                                                     node2vec_params=dict(num_walks=150, q=0.25)))),
  5: dict(n_dims=112, combining_factor=0.1,
                           collaborative_params=dict(
                               prediction_network_params=dict(lr=0.05, epochs=100, batch_size=1536,
                                                              network_depth=3,
                                                              gaussian_noise=0.35, conv_depth=2,
                                                              kernel_l2=1e-9, dropout=0.0,),
                               user_item_params=dict(gcn_lr=0.00025, gcn_epochs=10, gcn_layers=2, gcn_dropout=0.0,
                                                     gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                     margin=1.0,
                                                     gaussian_noise=0.05,
                                                     node2vec_params=dict(num_walks=150, q=0.25)))),
          }
