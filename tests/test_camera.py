"""Tests for camera component."""

from unittest.mock import mock_open, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import CAMERA, COORDINATOR, DOMAIN
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_CUSTOM_IMG

pytestmark = pytest.mark.asyncio


async def test_update_file_path(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test update_file_path service."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_usps_camera")
        assert state.attributes.get("friendly_name") == "Mail USPS Camera"
        assert (
            "custom_components/mail_and_packages/mail_none.gif"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_usps_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/mail_none.gif"
            in state.attributes.get("file_path")
        )

        await hass.services.async_call(DOMAIN, "update_image")
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/mail_none.gif"
            in state.attributes.get("file_path")
        )

    # Unload the config
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load new config with custom img settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_usps_camera")
        assert state.attributes.get("friendly_name") == "Mail USPS Camera"
        assert "images/test.gif" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_usps_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test.gif" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test.gif" in caplog.text

    # TODO: Add process_mail and check camera file path


async def test_ups_camera(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test UPS camera functionality."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"
        assert (
            "custom_components/mail_and_packages/no_deliveries_ups.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_ups_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_ups.jpg"
            in state.attributes.get("file_path")
        )

    # Unload the config
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load new config with custom img settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"
        assert "images/test_ups.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_ups_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_ups.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_ups.jpg" in caplog.text


# async def test_check_file_path_access(
#     hass,
#     integration,
#     mock_imap_no_email,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_update_time,
#     mock_copy_overlays,
#     mock_hash_file,
#     mock_getctime_today,
#     mock_update,
#     caplog,
# ):
#     """Test check_file_path_access function."""
#     with patch("os.path.isfile", return_value=True), patch(
#         "os.access", return_value=False
#     ):
#         entry = integration
#         assert "Could not read camera" in caplog.text


async def test_async_camera_image(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test async_camera_image function."""

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=False
    ):
        entry = integration

        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            image = await cameras[0].async_camera_image()

        assert m_open.call_count == 1
        assert (
            "custom_components/mail_and_packages/mail_none.gif"
            in m_open.call_args.args[0]
        )
        assert m_open.call_args.args[1] == "rb"


async def test_async_camera_image_file_error(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
    caplog,
):
    """Test async_camera_image function."""

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=False
    ):
        entry = integration

        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            m_open.side_effect = FileNotFoundError
            image = await cameras[0].async_camera_image()

        assert "Could not read camera" in caplog.text


async def test_async_on_demand_update(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test async_camera_image function."""

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=False
    ):
        entry = integration

        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            image = await cameras[0].async_on_demand_update()

        assert image is None


async def test_amazon_camera_custom_img(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera with custom image settings."""
    # Load new config with custom img settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_amazon_delivery_camera_2")
        assert state.attributes.get("friendly_name") == "Mail Amazon Delivery Camera"
        assert "images/test_amazon.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_amazon_delivery_camera_2"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_amazon.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_amazon.jpg" in caplog.text


async def test_ups_camera_with_image_data(
    hass,
    integration,
    mock_imap_ups_delivered_with_photo,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test UPS camera with image data."""
    entry = integration

    # Mock coordinator data with UPS image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "ups_image": "test_ups_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        ups_camera = None
        for camera in cameras:
            if camera._type == "ups_camera":
                ups_camera = camera
                break

        ups_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_ups_camera")

        # Check that it's using the UPS image path
        assert "test_ups_image.jpg" in state.attributes.get("file_path")


async def test_amazon_camera_with_image_data(
    hass,
    integration,
    mock_imap_amazon_delivered,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera with image data."""
    entry = integration

    # Mock coordinator data with Amazon image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "amazon_image": "test_amazon_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_amazon_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Amazon Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        amazon_camera = None
        for camera in cameras:
            if camera._type == "amazon_camera":
                amazon_camera = camera
                break

        amazon_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_amazon_delivery_camera")

        # Check that it's using the Amazon image path
        assert "test_amazon_image.jpg" in state.attributes.get("file_path")


async def test_ups_camera_with_custom_image(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test UPS camera with custom image functionality."""
    # Unload the default config
    entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load config with custom UPS image settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"
        assert "images/test_ups.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_ups_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_ups.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_ups.jpg" in caplog.text


async def test_amazon_camera_with_custom_image(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera with custom image functionality."""
    # Unload the default config
    entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load config with custom Amazon image settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_amazon_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Amazon Delivery Camera"
        assert "images/test_amazon.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_amazon_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_amazon.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_amazon.jpg" in caplog.text


async def test_ups_camera_default_image_path(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test UPS camera uses correct default image path."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"
        # Should use the new UPS-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_ups.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_ups_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_ups.jpg"
            in state.attributes.get("file_path")
        )


async def test_amazon_camera_default_image_path(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera uses correct default image path."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_amazon_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Amazon Delivery Camera"
        # Should use the new Amazon-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_amazon_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
            in state.attributes.get("file_path")
        )


async def test_camera_entity_creation(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test that all camera entities are created correctly."""
    entry = integration

    # Check that all expected camera entities exist
    expected_cameras = [
        "camera.mail_usps_camera",
        "camera.mail_amazon_delivery_camera",
        "camera.mail_ups_camera",
    ]

    for camera_entity in expected_cameras:
        state = hass.states.get(camera_entity)
        assert state is not None, f"Camera entity {camera_entity} should exist"
        assert state.attributes.get("friendly_name") is not None
        assert state.attributes.get("file_path") is not None


async def test_camera_image_update_service(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test camera image update service works for all cameras."""
    entry = integration

    cameras_to_test = [
        "camera.mail_usps_camera",
        "camera.mail_amazon_delivery_camera",
        "camera.mail_ups_camera",
    ]

    for camera_entity in cameras_to_test:
        with patch("os.path.isfile", return_value=True), patch(
            "os.access", return_value=True
        ):
            state_before = hass.states.get(camera_entity)
            assert state_before is not None

            service_data = {"entity_id": camera_entity}
            await hass.services.async_call(DOMAIN, "update_image", service_data)
            await hass.async_block_till_done()

            state_after = hass.states.get(camera_entity)
            assert state_after is not None
            # The file path should remain the same after update
            assert state_after.attributes.get(
                "file_path"
            ) == state_before.attributes.get("file_path")
