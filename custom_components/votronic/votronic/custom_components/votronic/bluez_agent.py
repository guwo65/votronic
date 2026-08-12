from __future__ import annotations

import logging

from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType
from dbus_fast.errors import DBusError
from dbus_fast.service import ServiceInterface, method

_LOGGER = logging.getLogger(__name__)

BLUEZ_SERVICE = "org.bluez"
BLUEZ_MANAGER_PATH = "/org/bluez"
BLUEZ_MANAGER_INTERFACE = "org.bluez.AgentManager1"

AGENT_PATH = "/com/homeassistant/votronic_agent"
AGENT_CAPABILITY = "KeyboardOnly"

VOTRONIC_ADDRESS = "0C:43:14:33:80:72"
VOTRONIC_PIN = "173928"

EXPECTED_DEVICE_PATH = (
    "/org/bluez/hci0/dev_"
    + VOTRONIC_ADDRESS.replace(":", "_")
)


class VotronicPairingAgent(ServiceInterface):
    """BlueZ pairing agent restricted to the Votronic connector."""

    def __init__(self) -> None:
        super().__init__("org.bluez.Agent1")

    def _check_device(self, device: str) -> None:
        """Reject pairing requests from every other Bluetooth device."""

        if device != EXPECTED_DEVICE_PATH:
            _LOGGER.warning(
                "Rejecting BlueZ pairing request from unexpected device %s",
                device,
            )
            raise DBusError(
                "org.bluez.Error.Rejected",
                "Pairing agent is restricted to the Votronic connector",
            )

    @method()
    def Release(self) -> "":
        """BlueZ released the agent."""

        _LOGGER.warning("VOTRONIC BLUEZ AGENT RELEASED")

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        """Return the legacy Bluetooth PIN."""

        self._check_device(device)

        _LOGGER.warning(
            "VOTRONIC BLUEZ AGENT RequestPinCode | "
            "DEVICE=%s | RETURNING PIN",
            device,
        )

        return VOTRONIC_PIN

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        """Return the numeric BLE passkey."""

        self._check_device(device)

        _LOGGER.warning(
            "VOTRONIC BLUEZ AGENT RequestPasskey | "
            "DEVICE=%s | RETURNING PASSKEY",
            device,
        )

        return int(VOTRONIC_PIN)

    @method()
    def RequestConfirmation(
        self,
        device: "o",
        passkey: "u",
    ) -> "":
        """Confirm only the expected Votronic passkey."""

        self._check_device(device)

        _LOGGER.warning(
            "VOTRONIC BLUEZ AGENT RequestConfirmation | "
            "DEVICE=%s | PASSKEY=%06d",
            device,
            passkey,
        )

        if passkey != int(VOTRONIC_PIN):
            raise DBusError(
                "org.bluez.Error.Rejected",
                "Unexpected Votronic passkey",
            )

    @method()
    def RequestAuthorization(self, device: "o") -> "":
        """Authorize the expected connector."""

        self._check_device(device)

        _LOGGER.warning(
            "VOTRONIC BLUEZ AGENT RequestAuthorization | DEVICE=%s",
            device,
        )

    @method()
    def AuthorizeService(
        self,
        device: "o",
        uuid: "s",
    ) -> "":
        """Authorize services only for the expected connector."""

        self._check_device(device)

        _LOGGER.warning(
            "VOTRONIC BLUEZ AGENT AuthorizeService | "
            "DEVICE=%s | UUID=%s",
            device,
            uuid,
        )

    @method()
    def Cancel(self) -> "":
        """BlueZ cancelled the pairing request."""

        _LOGGER.warning("VOTRONIC BLUEZ AGENT PAIRING CANCELLED")


class BlueZAgentRegistration:
    """Manage registration of the temporary Votronic pairing agent."""

    def __init__(self) -> None:
        self.bus: MessageBus | None = None
        self.manager = None
        self.agent = VotronicPairingAgent()
        self.registered = False

    async def register(self) -> None:
        """Export and register the agent."""

        _LOGGER.warning(
            "===== VOTRONIC BLUEZ AGENT REGISTER START ====="
        )

        self.bus = await MessageBus(
            bus_type=BusType.SYSTEM
        ).connect()

        self.bus.export(
            AGENT_PATH,
            self.agent,
        )

        introspection = await self.bus.introspect(
            BLUEZ_SERVICE,
            BLUEZ_MANAGER_PATH,
        )

        proxy = self.bus.get_proxy_object(
            BLUEZ_SERVICE,
            BLUEZ_MANAGER_PATH,
            introspection,
        )

        self.manager = proxy.get_interface(
            BLUEZ_MANAGER_INTERFACE
        )

        await self.manager.call_register_agent(
            AGENT_PATH,
            AGENT_CAPABILITY,
        )

        self.registered = True

        #
        # Bleak uses another D-Bus connection. Making this agent the
        # default allows it to handle the pairing initiated by Bleak.
        #
        await self.manager.call_request_default_agent(
            AGENT_PATH
        )

        _LOGGER.warning(
            "===== VOTRONIC BLUEZ AGENT REGISTERED ====="
        )

    async def unregister(self) -> None:
        """Unregister and disconnect the temporary agent."""

        if self.registered and self.manager is not None:
            try:
                await self.manager.call_unregister_agent(
                    AGENT_PATH
                )
            except Exception:
                _LOGGER.debug(
                    "Could not unregister Votronic BlueZ agent",
                    exc_info=True,
                )

        self.registered = False

        if self.bus is not None:
            try:
                self.bus.unexport(AGENT_PATH)
                self.bus.disconnect()
            except Exception:
                _LOGGER.debug(
                    "Could not close Votronic BlueZ agent bus",
                    exc_info=True,
                )

        self.bus = None
        self.manager = None

        _LOGGER.warning(
            "===== VOTRONIC BLUEZ AGENT UNREGISTERED ====="
        )