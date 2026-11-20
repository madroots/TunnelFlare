import uuid

from tunnelflare_gui.single_instance import listen_for_activation, notify_running_instance


def test_second_launch_brings_the_first_instance_forward(qapp, qtbot):
    name = f"TunnelFlare-test-{uuid.uuid4().hex[:12]}"
    assert notify_running_instance(name) is False  # nothing running yet

    activations = []
    server = listen_for_activation(lambda: activations.append(True), None, name)
    try:
        assert notify_running_instance(name) is True
        qtbot.waitUntil(lambda: bool(activations))
    finally:
        server.close()
