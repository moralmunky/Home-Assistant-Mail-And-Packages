"""Tests for camera component."""

import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.camera import MailCam
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

        await ups_camera.update_file_path()
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

        await amazon_camera.update_file_path()
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
        "camera.mail_walmart_camera",
        "camera.mail_generic_delivery_camera",
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
        "camera.mail_walmart_camera",
        "camera.mail_generic_delivery_camera",
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


async def test_generic_camera(
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
    """Test Generic camera functionality."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"
        assert (
            "custom_components/mail_and_packages/no_deliveries_generic.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_generic.jpg"
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
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"
        assert "images/test_generic.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_generic.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_generic.jpg" in caplog.text


async def test_generic_camera_with_delivery_images(
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
    """Test Generic camera with delivery images from other cameras."""
    entry = integration

    # Mock coordinator data with Amazon delivery image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "amazon_image": "test_amazon_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "amazon_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Check that it's using the Amazon delivery image
        assert "test_amazon_delivery.jpg" in state.attributes.get("file_path")


async def test_generic_camera_with_ups_delivery_images(
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
    """Test Generic camera with UPS delivery images."""
    entry = integration

    # Mock coordinator data with UPS delivery image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "ups_image": "test_ups_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "ups_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Check that it's using the UPS delivery image
        assert "test_ups_delivery.jpg" in state.attributes.get("file_path")


async def test_generic_camera_with_walmart_delivery_images(
    hass,
    integration,
    mock_imap_walmart_delivered_with_photo,
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
    """Test Generic camera with Walmart delivery images."""
    entry = integration

    # Mock coordinator data with Walmart delivery image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "walmart_image": "test_walmart_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "walmart_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Check that it's using the Walmart delivery image
        assert "test_walmart_delivery.jpg" in state.attributes.get("file_path")


async def test_generic_camera_with_usps_delivery_images_manual(
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
    """Test Generic camera without USPS (USPS removed from generic camera)."""
    entry = integration

    # Mock coordinator data with USPS delivery image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # Even if USPS is delivered, generic camera should ignore it
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Check that it's using the default no deliveries image (USPS removed from generic camera)
        assert "no_deliveries_generic.jpg" in state.attributes.get("file_path")


async def test_generic_camera_with_all_delivery_types(
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
    """Test Generic camera with all delivery types (Amazon, UPS, Walmart) to create animated GIF."""
    entry = integration

    # Mock coordinator data with all delivery types (excluding USPS)
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # Amazon delivery
        "amazon_image": "test_amazon_delivery.jpg",
        "amazon_delivered": 1,
        # UPS delivery
        "ups_image": "test_ups_delivery.jpg",
        "ups_delivered": 1,
        # Walmart delivery
        "walmart_image": "test_walmart_delivery.jpg",
        "walmart_delivered": 1,
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch(
        "PIL.Image.open"
    ) as mock_pil_open:
        # Mock PIL Image objects
        mock_image = MagicMock()
        mock_pil_open.return_value = mock_image

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with all 3 delivery images (excluding USPS)
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert (
            "Generic camera - created animated GIF with 3 delivery images"
            in caplog.text
        )

        # Verify PIL was called to create animated GIF
        mock_pil_open.assert_called()
        mock_image.save.assert_called_once()


async def test_generic_camera_filters_no_mail_images(
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
    """Test Generic camera properly filters out 'no mail' images."""
    entry = integration

    # Mock coordinator data with mix of delivery and "no mail" images
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # Amazon - actual delivery
        "amazon_image": "test_amazon_delivery.jpg",
        "amazon_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # UPS - no mail image (should be filtered out)
        "ups_image": "no_deliveries_ups.jpg",
        "ups_delivered": 0,  # No deliveries, should be filtered out
        # USPS - no mail image (should be filtered out)
        "image_name": "mail_none.gif",
        "usps_delivered": 0,  # No deliveries, should be filtered out
        # Walmart - actual delivery
        "walmart_image": "test_walmart_delivery.jpg",
        "walmart_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch(
        "PIL.Image.open"
    ) as mock_pil_open:
        # Mock PIL Image objects
        mock_image = MagicMock()
        mock_pil_open.return_value = mock_image

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with only 2 actual delivery images (Amazon and Walmart)
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert (
            "Generic camera - created animated GIF with 2 delivery images"
            in caplog.text
        )

        # Verify PIL was called to create animated GIF
        mock_pil_open.assert_called()
        mock_image.save.assert_called_once()


async def test_generic_camera_respects_enabled_sensors(
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
    """Test Generic camera only includes cameras whose sensors are enabled in config."""
    entry = integration

    # Mock coordinator data with all delivery types
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # Amazon delivery
        "amazon_image": "test_amazon_delivery.jpg",
        "amazon_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # UPS delivery
        "ups_image": "test_ups_delivery.jpg",
        "ups_delivered": 1,  # UPS has deliveries but sensor will be disabled
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # USPS has deliveries but sensor will be disabled
        # Walmart delivery
        "walmart_image": "test_walmart_delivery.jpg",
        "walmart_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    # Mock config to only enable Amazon and Walmart sensors
    # Create a new data dict with only Amazon and Walmart enabled
    new_data = entry.data.copy()
    new_data["resources"] = [
        "amazon_delivered",
        "walmart_delivered",
    ]  # Only Amazon and Walmart enabled

    # Update the entry using the proper Home Assistant method
    hass.config_entries.async_update_entry(entry, data=new_data)

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch(
        "PIL.Image.open"
    ) as mock_pil_open:
        # Mock PIL Image objects
        mock_image = MagicMock()
        mock_pil_open.return_value = mock_image

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with only 2 delivery images (Amazon and Walmart)
        # UPS and USPS should be skipped because their sensors are not enabled
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert (
            "Generic camera - created animated GIF with 2 delivery images"
            in caplog.text
        )
        assert (
            "Generic camera - skipping ups (sensor ups_delivered not enabled)"
            in caplog.text
        )
        # Note: USPS is now skipped entirely in generic camera, not just when sensor is disabled

        # Verify PIL was called to create animated GIF
        mock_pil_open.assert_called()
        mock_image.save.assert_called_once()


async def test_generic_camera_with_custom_image(
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
    """Test Generic camera with custom image functionality."""
    # Unload the default config
    entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load config with custom Generic image settings
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
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"
        assert "images/test_generic.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_generic.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_generic.jpg" in caplog.text


async def test_generic_camera_default_image_path(
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
    """Test Generic camera uses correct default image path."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"
        # Should use the new Generic-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_generic.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_generic.jpg"
            in state.attributes.get("file_path")
        )


async def test_generic_camera_with_usps_delivery_images(
    hass,
    integration,
    mock_imap_usps_delivered_individual,
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
    """Test Generic camera without USPS (USPS removed from generic camera)."""
    entry = integration

    # Mock coordinator data with USPS delivery
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # Even if USPS is delivered, generic camera should ignore it
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        generic_camera = None
        for camera in cameras:
            if camera._type == "generic_camera":
                generic_camera = camera
                break

        if generic_camera:
            await generic_camera.update_file_path()
            await hass.async_block_till_done()

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Should use default no deliveries image since USPS is removed from generic camera
        file_path = state.attributes.get("file_path")
        assert file_path is not None
        # The file path should contain the default no deliveries image
        assert "no_deliveries_generic.jpg" in file_path

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        file_path = state.attributes.get("file_path")
        assert file_path is not None
        # The file path should contain the default no deliveries image
        assert "no_deliveries_generic.jpg" in file_path
        assert "Generic camera - no deliveries found, using default" in caplog.text


async def test_generic_camera_with_multiple_delivery_images(
    hass,
    integration,
    mock_imap_amazon_delivered,
    mock_imap_ups_delivered_with_photo,
    mock_imap_usps_delivered_individual,
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
    """Test Generic camera with multiple delivery images (Amazon, UPS). USPS is excluded."""
    entry = integration

    # Mock coordinator data with multiple delivery types
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # Amazon delivery
        "amazon_image": "test_amazon_delivery.jpg",
        "amazon_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # UPS delivery
        "ups_image": "test_ups_delivery.jpg",
        "ups_delivered": 1,  # Need delivery count > 0 for generic camera to include it
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # Even if USPS is delivered, generic camera should ignore it
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch(
        "PIL.Image.open"
    ) as mock_pil_open:
        # Mock PIL Image objects
        mock_image = MagicMock()
        mock_pil_open.return_value = mock_image

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        # Should create animated GIF with multiple delivery images
        # Get the updated state after the service call
        state = hass.states.get("camera.mail_generic_delivery_camera")
        file_path = state.attributes.get("file_path")
        assert file_path is not None
        assert "generic_deliveries.gif" in file_path
        assert "Generic camera - created animated GIF with" in caplog.text
        assert "2 delivery images" in caplog.text

        # Verify PIL was called to create animated GIF
        mock_pil_open.assert_called()
        mock_image.save.assert_called_once()


async def test_walmart_camera(
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
    """Test Walmart camera functionality."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_walmart_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Camera"
        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_walmart_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
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
        state = hass.states.get("camera.mail_walmart_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Camera"
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_walmart_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_walmart.jpg" in caplog.text


async def test_walmart_camera_with_image_data(
    hass,
    integration,
    mock_imap_walmart_delivered_with_photo,
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
    """Test Walmart camera with image data."""
    entry = integration

    # Mock coordinator data with Walmart image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "walmart_image": "test_walmart_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_walmart_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        walmart_camera = None
        for camera in cameras:
            if camera._type == "walmart_camera":
                walmart_camera = camera
                break

        await walmart_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_walmart_camera")

        # Check that it's using the Walmart image path
        assert "test_walmart_image.jpg" in state.attributes.get("file_path")


async def test_walmart_camera_with_custom_image(
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
    """Test Walmart camera with custom image functionality."""
    # Unload the default config
    entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load config with custom Walmart image settings
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
        state = hass.states.get("camera.mail_walmart_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Camera"
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_walmart_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_walmart.jpg" in caplog.text


async def test_walmart_camera_default_image_path(
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
    """Test Walmart camera uses correct default image path."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ):
        state = hass.states.get("camera.mail_walmart_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Camera"
        # Should use the new Walmart-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_walmart_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )


async def test_camera_update_no_data():
    """Test camera update when coordinator has no data."""
    # Create a mock coordinator with no data
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = None

    # Create camera
    camera = MailCam(
        hass=MagicMock(),
        name="usps_camera",
        config=MagicMock(),
        coordinator=mock_coordinator,
    )

    # Mock the update_file_path method
    with patch.object(camera, "update_file_path") as mock_update:
        await camera.async_update()

        # Should call update_file_path but it should return early when data is None
        mock_update.assert_called_once()


async def test_camera_update_coordinator_failure():
    """Test camera update when coordinator update failed."""
    # Create a mock coordinator with failed update
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False

    # Create camera
    camera = MailCam(
        hass=MagicMock(),
        name="usps_camera",
        config=MagicMock(),
        coordinator=mock_coordinator,
    )

    # Mock the update_file_path method
    with patch.object(camera, "update_file_path") as mock_update:
        await camera.async_update()

        # Should call update_file_path but it should return early when data is None
        mock_update.assert_called_once()


async def test_camera_custom_no_mail_image():
    """Test camera with custom no-mail image configuration."""
    # Create a mock coordinator with data
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {"usps_delivered": 0}

    # Create mock config with custom image from existing test data
    mock_config = MagicMock()
    mock_config.data = FAKE_CONFIG_DATA_CUSTOM_IMG.copy()

    # Create camera
    camera = MailCam(
        hass=MagicMock(),
        name="usps_camera",
        config=mock_config,
        coordinator=mock_coordinator,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file
        test_file = os.path.join(temp_dir, "no_mail.gif")
        with open(test_file, "w") as f:
            f.write("test")

        # Mock os.path.exists to return True for the custom file
        with patch("os.path.exists", return_value=True):
            # Test the _is_custom_no_mail_image method
            result = camera._is_custom_no_mail_image("usps", "images/test.gif")

            # Should return True for custom no-mail image
            assert result is True
