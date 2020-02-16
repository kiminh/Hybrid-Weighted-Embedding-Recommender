params = {
    1: dict(n_dims=64, combining_factor=0.1,
                               collaborative_params=dict(
                                   prediction_network_params=dict(lr=0.03, epochs=50, batch_size=1024,
                                                                  network_depth=2, scorer_depth=2,
                                                                  gaussian_noise=0.175, conv_depth=2,
                                                                  kernel_l2=1e-9, dropout=0.0),
                                   user_item_params=dict(lr=0.1, epochs=20, batch_size=64, l2=0.0001,
                                                         gcn_lr=0.001, gcn_epochs=10, gcn_layers=2, gcn_dropout=0.0,
                                                         gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                         margin=1.0,
                                                         gaussian_noise=0.15,))),
    2: dict(n_dims=64, combining_factor=0.1,
                               collaborative_params=dict(
                                   prediction_network_params=dict(lr=0.03, epochs=50, batch_size=1024,
                                                                  network_depth=3, scorer_depth=3,
                                                                  gaussian_noise=0.2, conv_depth=2,
                                                                  kernel_l2=1e-9, dropout=0.0),
                                   user_item_params=dict(lr=0.1, epochs=20, batch_size=64, l2=0.0001,
                                                         gcn_lr=0.001, gcn_epochs=10, gcn_layers=2, gcn_dropout=0.0,
                                                         gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                         margin=1.0,
                                                         gaussian_noise=0.15,))),
    3: dict(n_dims=64, combining_factor=0.1,
                               collaborative_params=dict(
                                   prediction_network_params=dict(lr=0.05, epochs=50, batch_size=1024,
                                                                  network_depth=3, scorer_depth=3,
                                                                  gaussian_noise=0.15, conv_depth=2,
                                                                  kernel_l2=1e-9, dropout=0.0),
                                   user_item_params=dict(lr=0.1, epochs=20, batch_size=64, l2=0.0001,
                                                         gcn_lr=0.001, gcn_epochs=10, gcn_layers=2, gcn_dropout=0.0,
                                                         gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                         margin=1.0,
                                                         gaussian_noise=0.05,))),
    4: dict(n_dims=64, combining_factor=0.1,
                               collaborative_params=dict(
                                   prediction_network_params=dict(lr=0.05, epochs=50, batch_size=1024,
                                                                  network_depth=3, scorer_depth=3,
                                                                  gaussian_noise=0.175, conv_depth=2,
                                                                  kernel_l2=1e-9, dropout=0.0),
                                   user_item_params=dict(lr=0.1, epochs=20, batch_size=64, l2=0.0001,
                                                         gcn_lr=0.001, gcn_epochs=10, gcn_layers=2, gcn_dropout=0.0,
                                                         gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=2,
                                                         margin=1.0,
                                                         gaussian_noise=0.05,))),
    5: dict(n_dims=64, combining_factor=0.1,
                               collaborative_params=dict(
                                   prediction_network_params=dict(lr=0.05, epochs=55, batch_size=1024,
                                                                  network_depth=4, scorer_depth=4,
                                                                  gaussian_noise=0.15, conv_depth=4,
                                                                  kernel_l2=1e-9, dropout=0.0),
                                   user_item_params=dict(lr=0.1, epochs=20, batch_size=64, l2=0.0001,
                                                         gcn_lr=0.001, gcn_epochs=20, gcn_layers=3, gcn_dropout=0.0,
                                                         gcn_kernel_l2=1e-8, gcn_batch_size=1024, conv_depth=3,
                                                         margin=1.0,
                                                         gaussian_noise=0.025,)))
}
