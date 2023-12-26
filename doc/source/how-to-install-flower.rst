Install Flower
==============


Python version
--------------

Flower requires at least `Python 3.8 <https://docs.python.org/3.8/>`_, but `Python 3.10 <https://docs.python.org/3.10/>`_ or above is recommended.


Install stable release
----------------------

Stable releases are available on `PyPI <https://pypi.org/project/flwr/>`_::

  python -m pip install flwr

For simulations that use the Virtual Client Engine, ``flwr`` should be installed with the ``simulation`` extra::

  python -m pip install flwr[simulation]


Verify installation
-------------------

The following command can be used to verify if Flower was successfully installed. If everything worked, it should print the version of Flower to the command line::

  python -c "import flwr;print(flwr.__version__)"
  1.5.0


Advanced installation options
-----------------------------

Install via Docker
~~~~~~~~~~~~~~~~~~

`How to run Flower using Docker <https://flower.dev/docs/framework/how-to-run-flower-using-docker.html>`_

Install pre-release
~~~~~~~~~~~~~~~~~~~

New (possibly unstable) versions of Flower are sometimes available as pre-release versions (alpha, beta, release candidate) before the stable release happens::

  python -m pip install -U --pre flwr

For simulations that use the Virtual Client Engine, ``flwr`` pre-releases should be installed with the ``simulation`` extra::

  python -m pip install -U --pre flwr[simulation]

Install nightly release
~~~~~~~~~~~~~~~~~~~~~~~

The latest (potentially unstable) changes in Flower are available as nightly releases::

  python -m pip install -U flwr-nightly

For simulations that use the Virtual Client Engine, ``flwr-nightly`` should be installed with the ``simulation`` extra::

  python -m pip install -U flwr-nightly[simulation]
