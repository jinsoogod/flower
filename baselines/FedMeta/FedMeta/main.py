"""Create and connect the building blocks for your experiments; start the simulation.

It includes processioning the dataset, instantiate strategy, specify how the global
model is going to be evaluated, etc. At the end, this script saves the results.
"""
# these are the basic packages you'll need here
# feel free to remove some if aren't needed
import hydra
from omegaconf import DictConfig, OmegaConf
from hydra.utils import instantiate
from strategy import weighted_average
from dataset import load_datasets
from Fedmeta_client_manager import Fedmeta_client_manager

import flwr as fl
import client


@hydra.main(config_path="conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    """Run the baseline.

    Parameters
    ----------
    cfg : DictConfig
        An omegaconf object that stores the hydra config.
    """
    # print config structured as YAML
    print(OmegaConf.to_yaml(cfg))

    # partition dataset and get dataloaders
    trainloaders, valloaders, testloaders= load_datasets(config=cfg.data, path=cfg.path)

    # prepare function that will be used to spawn each client
    client_fn = client.gen_client_fn(
        num_epochs=cfg.num_epochs,
        trainloaders=trainloaders,
        valloaders=valloaders,
        learning_rate=cfg.algo[cfg.data.data].alpha,
        model=cfg.data.model,
        gradient_step=cfg.data.gradient_step,
    )

    # prepare strategy function
    strategy = instantiate(
        cfg.strategy,
        evaluate_metrics_aggregation_fn=weighted_average,
        alpha=cfg.algo[cfg.data.data].alpha,
        beta=cfg.algo[cfg.data.data].beta,
        data=cfg.data.data,
        algo=cfg.algo.algo,
    )

    # Start Simulation
    history = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=len(trainloaders['sup']),
        config=fl.server.ServerConfig(num_rounds=cfg.data.num_rounds),
        client_resources={
            "num_cpus": cfg.data.client_resources.num_cpus,
            "num_gpus": cfg.data.client_resources.num_gpus,
        },
        client_manager=Fedmeta_client_manager(valid_client=len(valloaders['qry'])),
        strategy=strategy,
    )

    # 6. Save your results
    # Here you can save the `history` returned by the simulation and include
    # also other buffers, statistics, info needed to be saved in order to later
    # on generate the plots you provide in the README.md. You can for instance
    # access elements that belong to the strategy for example:
    # data = strategy.get_my_custom_data() -- assuming you have such method defined.
    # Hydra will generate for you a directory each time you run the code. You
    # can retrieve the path to that directory with this:
    # save_path = HydraConfig.get().runtime.output_dir


if __name__ == "__main__":
    main()