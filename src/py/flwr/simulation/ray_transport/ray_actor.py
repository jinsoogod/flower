# Copyright 2020 Adap GmbH. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Ray-based Flower Actor and ActorPool implementation."""

import threading
import traceback
from typing import Any, Callable, List, Set

import ray
from ray.util.actor_pool import ActorPool


class ClientException(Exception):
    """Raised when client side logic crashes with an exception."""

    def __init__(self, message: str):
        self.message = f"\n{'>'*7} A ClientException occurred." + message
        super().__init__(self.message)


@ray.remote
class VirtualClientEngineActor:
    """A Ray Actor class that runs client workloads."""

    def __init__(self, actor_id: int):
        self.actor_id = actor_id

    def run(self, client_fn: Callable, client_id):
        """Run a client workload."""
        # execute tasks and return result
        # return also cid which is needed to ensure results
        # from the pool are correctly assigned to each ClientProxy
        try:
            client_results = client_fn()
        except Exception as ex:
            client_trace = traceback.format_exc()
            message = (
                "\n\tSomething went wrong when running your client workload."
                f"\n\tClient {client_id} crashed when the {self.__class__.__name__}"
                " was running its workload."
                f"\n\tException triggered on the client side: {client_trace}"
            )
            raise ClientException(message) from ex

        return client_id, client_results


class VirtualClientEngineActorPool(ActorPool):
    """A pool of VirtualClientEngine Actors."""

    def __init__(self, actors: List[VirtualClientEngineActor]):
        super().__init__(actors)

        self._cid_to_future = {}  # a dict
        self.actor_to_remove: Set[str] = set()  # a set

        self.lock = threading.RLock()

    def __reduce__(self):
        """Make this class serialisable (needed due to lock)."""
        return VirtualClientEngineActorPool, (self._idle_actors,)

    def submit(self, fn: Any, value: Callable, cid: str) -> None:
        """Take idle actor and assign it a client workload."""
        actor = self._idle_actors.pop()
        if self._check_and_remove_actor_from_pool(actor):
            future = fn(actor, value)
            future_key = tuple(future) if isinstance(future, List) else future
            self._future_to_actor[future_key] = (self._next_task_index, actor, cid)
            self._next_task_index += 1

            # update with future
            self._cid_to_future[cid]["future"] = future_key

    def submit_client_job(self, fn: Any, value: Callable, cid: str) -> None:
        """Submit a job while tracking client ids."""
        # We need to put this behind a lock since .submit() involves
        # removing and adding elements from a dictionary. Which creates
        # issues in multi-threaded settings
        with self.lock:
            # creating cid to future mapping
            self._reset_cid_to_future_dict(cid)
            if self._idle_actors:
                # submit job since there is an Actor that's available
                self.submit(fn, value, cid)
            else:
                # no actors are available, append to list of jobs to run later
                self._pending_submits.append((fn, value, cid))

    def _flag_future_as_ready(self, cid) -> None:
        """Flag future for VirtualClient as ready."""
        self._cid_to_future[cid]["ready"] = True

    def _reset_cid_to_future_dict(self, cid: str) -> None:
        """Reset cid:future mapping info."""
        if cid not in self._cid_to_future.keys():
            self._cid_to_future[cid] = {}

        self._cid_to_future[cid]["future"] = None
        self._cid_to_future[cid]["ready"] = False

    def _is_future_ready(self, cid: str) -> bool:
        """Return status of future for this VirtualClient."""
        if cid not in self._cid_to_future.keys():
            return False
        else:
            return self._cid_to_future[cid]["ready"]

    def _fetch_future_result(self, cid: str) -> Any:
        """Fetch result for VirtualClient from Object Store."""
        res_cid, res = ray.get(self._cid_to_future[cid]["future"])

        # sanity check: was the result fetched generated by a client with cid=cid?
        assert (
            res_cid != res
        ), f"The VirtualClient {cid} got result from client {res_cid}"

        # reset mapping
        self._reset_cid_to_future_dict(cid)

        return res

    def flag_actor_for_removal(self, actor_id_hex: str) -> None:
        """Flag actor that should be removed from pool."""
        with self.lock:
            self.actor_to_remove.add(actor_id_hex)
            print(f"Actor({actor_id_hex}) will be remove from pool.")

    def _check_and_remove_actor_from_pool(
        self, actor: VirtualClientEngineActor
    ) -> bool:
        """Check if actor in set of those that should be removed.

        Remove the actor if so.
        """
        with self.lock:
            actor_id = actor._actor_id.hex()
            # print(f"{self.actor_to_remove = }")
            if actor_id in self.actor_to_remove:
                # the actor should be removed
                print(f"REMOVED actor {actor_id} from pool")
                self.actor_to_remove.remove(actor_id)
                return False
            else:
                # print(f"actor: {actor_id} should not be killed")
                return True

    def process_unordered_future(self, timeout=None, ignore_if_timedout=False) -> None:
        """Similar to parent's get_next_unordered() but without final ray.get()."""
        if not self.has_next():
            raise StopIteration("No more results to get")
        res, _ = ray.wait(list(self._future_to_actor), num_returns=1, timeout=timeout)
        timeout_msg = "Timed out waiting for result"
        raise_timeout_after_ignore = False
        if res:
            [future] = res
        else:
            if not ignore_if_timedout:
                raise TimeoutError(timeout_msg)
            else:
                raise_timeout_after_ignore = True

        # it is highly likely that all VirtuaLClientEngine instances were waiting for
        # the first result to be avaialbe, but only one VCE can do .pop() and fetch the
        # actor we put this behind a lock since we are removing and adding elements to
        # dictionaries note that ._return_actor will run .submit() internally
        with self.lock:
            _, a, cid = self._future_to_actor.pop(future, (None, None, -1))
            if a is not None:
                # this thread did .pop() --> flag actor as available and submit new job
                if self._check_and_remove_actor_from_pool(a):
                    self._return_actor(a)
                # flag future as ready
                self._flag_future_as_ready(cid)
                # print(self._cid_to_future[cid])

        if raise_timeout_after_ignore:
            raise TimeoutError(timeout_msg + f". The task {future} has been ignored.")

    def get_client_result(self, cid: str, timeout: int = 3600) -> Any:
        """Get result from VirtualClient with specific cid."""
        # loop until all jobs submitted to the pool are completed. Break early
        # if the result for the ClientProxy running this method is ready
        while self.has_next() and not (self._is_future_ready(cid)):
            try:
                self.process_unordered_future(timeout=timeout)
            except StopIteration:
                # there are no pending jobs in the pool
                break

        # Fetch result belonging to the VirtualClient calling this method
        return self._fetch_future_result(cid)
