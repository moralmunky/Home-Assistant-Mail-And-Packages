"""Tests for camera component."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from homeassistant.const import ATTR_ENTITY_ID
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.camera import MailCam
from custom_components.mail_and_packages.const import (
    ATTR_AMAZON_IMAGE,
    ATTR_IMAGE_PATH,
    DOMAIN,
)
from tests.const import FAKE_CONFIG_DATA_CUSTOM_IMG

pytestmark = pytest.mark.asyncio


async def test_update_file_path(
    hass,
    mock_imap_no_email,
    integration,
    caplog,
):
    """Test update_file_path service."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
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
    mock_imap_no_email,
    integration,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
#     with patch("os.path.exists", return_value=True), patch(
#         "os.access", return_value=False
#     ):
#         entry = integration
#         assert "Could not read camera" in caplog.text


async def test_async_camera_image(
    hass,
    mock_imap_no_email,
    integration,
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
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=False),
    ):
        entry = integration

        cameras = entry.runtime_data.cameras
        with patch(
            "custom_components.mail_and_packages.camera.Path"
        ) as mock_path_class:
            mock_path_class.return_value.open.return_value.__enter__.return_value = (
                MagicMock(read=MagicMock(return_value=b""))
            )
            mock_path_class.return_value.open.return_value.__exit__ = MagicMock(
                return_value=False
            )
            await cameras[0].async_camera_image()

        assert mock_path_class.call_count == 1
        assert (
            "custom_components/mail_and_packages/mail_none.gif"
            in str(mock_path_class.call_args.args[0])
        )
        mock_path_class.return_value.open.assert_called_once_with("rb")


async def test_async_camera_image_file_error(
    hass,
    mock_imap_no_email,
    integration,
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
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=False),
    ):
        entry = integration

        cameras = entry.runtime_data.cameras
        with patch(
            "custom_components.mail_and_packages.camera.Path"
        ) as mock_path_class:
            mock_path_class.return_value.open.side_effect = FileNotFoundError
            await cameras[0].async_camera_image()

        assert "Could not read camera" in caplog.text


async def test_async_on_demand_update(
    hass,
    mock_imap_no_email,
    integration,
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
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=False),
    ):
        entry = integration

        cameras = entry.runtime_data.cameras
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            image = await cameras[0].async_on_demand_update()

        assert image is None


async def test_amazon_camera_custom_img(
    hass,
    mock_imap_no_email,
    integration,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_ups_delivered_with_photo,
    integration,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "ups_image": "test_ups_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        state = hass.states.get("camera.mail_ups_camera")
        assert state.attributes.get("friendly_name") == "Mail UPS Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera with image data."""
    # Setup integration manually to ensure mocks are active
    entry = integration

    # Mock coordinator data with Amazon image directly
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "amazon_image": "test_amazon_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        state = hass.states.get("camera.mail_amazon_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Amazon Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test UPS camera uses correct default image path."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Amazon camera uses correct default image path."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test that all camera entities are created correctly."""
    # Check that all expected camera entities exist
    expected_cameras = [
        "camera.mail_usps_camera",
        "camera.mail_amazon_delivery_camera",
        "camera.mail_ups_camera",
        "camera.mail_walmart_delivery_camera",
        "camera.mail_fedex_delivery_camera",
        "camera.mail_generic_delivery_camera",
    ]

    for camera_entity in expected_cameras:
        state = hass.states.get(camera_entity)
        assert state is not None, f"Camera entity {camera_entity} should exist"
        assert state.attributes.get("friendly_name") is not None
        assert state.attributes.get("file_path") is not None


async def test_camera_image_update_service(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test camera image update service works for all cameras."""
    cameras_to_test = [
        "camera.mail_usps_camera",
        "camera.mail_amazon_delivery_camera",
        "camera.mail_ups_camera",
        "camera.mail_walmart_delivery_camera",
        "camera.mail_fedex_delivery_camera",
        "camera.mail_generic_delivery_camera",
    ]

    def isfile_side_effect(path):
        return "mail_none.gif" in str(path)

    for camera_entity in cameras_to_test:
        with (
            patch("os.path.exists", side_effect=isfile_side_effect),
            patch("os.access", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            state_before = hass.states.get(camera_entity)
            assert state_before is not None

            service_data = {"entity_id": camera_entity}
            await hass.services.async_call(DOMAIN, "update_image", service_data)
            await hass.async_block_till_done()

            state_after = hass.states.get(camera_entity)
            assert state_after is not None


async def test_generic_camera(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_download_img,
    mock_imap_amazon_delivered,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "amazon_image": "test_amazon_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "amazon_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=["/fake/path/amazon/res1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
            return_value=True,
        ),
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
        assert "generic_deliveries.gif" in state.attributes.get("file_path")


async def test_generic_camera_with_ups_delivery_images(
    hass,
    mock_imap_ups_delivered_with_photo,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "ups_image": "test_ups_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "ups_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=["/fake/path/ups/res1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
            return_value=True,
        ),
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
        assert "generic_deliveries.gif" in state.attributes.get("file_path")


async def test_generic_camera_with_walmart_delivery_images(
    hass,
    mock_imap_walmart_delivered_with_photo,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "walmart_image": "test_walmart_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "walmart_delivered": 1,  # Need delivery count > 0 for generic camera to include it
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=["/fake/path/test_walmart_delivery_resized.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
            return_value=True,
        ),
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
        assert "generic_deliveries.gif" in state.attributes.get("file_path")


async def test_generic_camera_with_usps_delivery_images_manual(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # Even if USPS is delivered, generic camera should ignore it
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=[
                "/fake/path/test_amazon_delivery_resized.jpg",
                "/fake/path/test_ups_delivery_resized.jpg",
                "/fake/path/test_walmart_delivery_resized.jpg",
            ],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
        ) as mock_generate_gif,
    ):
        # Mock the generate_delivery_gif function to verify it's called correctly
        def mock_generate_gif_func(delivery_images, gif_path, duration=3000):
            # Verify we received the expected delivery images
            assert len(delivery_images) == 3, (
                f"Expected 3 delivery images, got {len(delivery_images)}"
            )
            # Verify the images are for Amazon, UPS, and Walmart
            # The paths should contain the image names from coordinator data
            assert any(
                coordinator.data.get("amazon_image").split(".")[0] in img
                for img in delivery_images
            ), f"Amazon image not found in {delivery_images}"
            assert any(
                coordinator.data.get("ups_image").split(".")[0] in img
                for img in delivery_images
            ), f"UPS image not found in {delivery_images}"
            assert any(
                coordinator.data.get("walmart_image").split(".")[0] in img
                for img in delivery_images
            ), f"Walmart image not found in {delivery_images}"
            # Verify the gif path
            assert "generic_deliveries.gif" in gif_path, (
                f"Expected generic_deliveries.gif in path, got {gif_path}"
            )
            return True

        mock_generate_gif.side_effect = mock_generate_gif_func

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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

        # Verify generate_delivery_gif was called to create animated GIF
        mock_generate_gif.assert_called_once()


async def test_generic_camera_filters_no_mail_images(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=[
                "/fake/path/test_amazon_delivery_resized.jpg",
                "/fake/path/test_walmart_delivery_resized.jpg",
            ],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
        ) as mock_generate_gif,
    ):
        # Mock the generate_delivery_gif function to verify it's called correctly
        def mock_generate_gif_func(delivery_images, gif_path, duration=3000):
            # Verify we received the expected delivery images (only Amazon and Walmart, no "no mail" images)
            assert len(delivery_images) == 2, (
                f"Expected 2 delivery images, got {len(delivery_images)}"
            )
            # Verify the images are for Amazon and Walmart (UPS and USPS "no mail" images should be filtered out)
            assert any(
                coordinator.data.get("amazon_image").split(".")[0] in img
                for img in delivery_images
            ), f"Amazon image not found in {delivery_images}"
            assert any(
                coordinator.data.get("walmart_image").split(".")[0] in img
                for img in delivery_images
            ), f"Walmart image not found in {delivery_images}"
            # Verify "no mail" images are NOT in the delivery images
            assert not any("no_deliveries" in img for img in delivery_images), (
                f"No mail images should not be in {delivery_images}"
            )
            assert not any("mail_none" in img for img in delivery_images), (
                f"USPS no mail image should not be in {delivery_images}"
            )
            # Verify the gif path
            assert "generic_deliveries.gif" in gif_path, (
                f"Expected generic_deliveries.gif in path, got {gif_path}"
            )
            return True

        mock_generate_gif.side_effect = mock_generate_gif_func

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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

        # Verify generate_delivery_gif was called to create animated GIF
        mock_generate_gif.assert_called_once()


async def test_generic_camera_respects_enabled_sensors(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
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
    await hass.async_block_till_done()

    # Get the camera reference before patching
    cameras = entry.runtime_data.cameras
    generic_camera = None
    for camera in cameras:
        if camera._type == "generic_camera":
            generic_camera = camera
            break

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=[
                "/fake/path/test_amazon_delivery_resized.jpg",
                "/fake/path/test_walmart_delivery_resized.jpg",
            ],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
        ) as mock_generate_gif,
    ):
        # Mock the generate_delivery_gif function to verify it's called correctly
        def mock_generate_gif_func(delivery_images, gif_path, duration=3000):
            # Verify we received the expected delivery images (only Amazon and Walmart)
            assert len(delivery_images) == 2, (
                f"Expected 2 delivery images, got {len(delivery_images)}"
            )
            # Verify the images are for Amazon and Walmart (UPS and USPS should be excluded)
            assert any(
                coordinator.data.get("amazon_image").split(".")[0] in img
                for img in delivery_images
            ), f"Amazon image not found in {delivery_images}"
            assert any(
                coordinator.data.get("walmart_image").split(".")[0] in img
                for img in delivery_images
            ), f"Walmart image not found in {delivery_images}"
            # Verify UPS and USPS are NOT in the delivery images
            assert not any(
                coordinator.data.get("ups_image").split(".")[0] in img
                for img in delivery_images
            ), f"UPS image should not be in {delivery_images}"
            # Verify the gif path
            assert "generic_deliveries.gif" in gif_path, (
                f"Expected generic_deliveries.gif in path, got {gif_path}"
            )
            return True

        mock_generate_gif.side_effect = mock_generate_gif_func

        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

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

        # Verify generate_delivery_gif was called to create animated GIF
        mock_generate_gif.assert_called_once()


async def test_generic_camera_with_custom_image(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_copyfile,
    caplog,
):
    """Test Generic camera uses correct default image path."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
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
    mock_imap_usps_delivered_individual,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        "usps_delivered": 1,  # Even if USPS is delivered, generic camera should ignore it
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
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
    mock_download_img,
    mock_imap_amazon_delivered,
    integration,
    mock_imap_ups_delivered_with_photo,
    mock_imap_usps_delivered_individual,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=[
                "/fake/path/test_amazon_delivery_resized.jpg",
                "/fake/path/test_ups_delivery_resized.jpg",
            ],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
        ) as mock_generate_gif,
    ):
        # Mock the generate_delivery_gif function to verify it's called correctly
        def mock_generate_gif_func(delivery_images, gif_path, duration=3000):
            # Verify we received the expected delivery images (Amazon and UPS, USPS excluded)
            assert len(delivery_images) == 2, (
                f"Expected 2 delivery images, got {len(delivery_images)}"
            )
            # Verify the images are for Amazon and UPS (USPS should be excluded)
            assert any(
                coordinator.data.get("amazon_image").split(".")[0] in img
                for img in delivery_images
            ), f"Amazon image not found in {delivery_images}"
            assert any(
                coordinator.data.get("ups_image").split(".")[0] in img
                for img in delivery_images
            ), f"UPS image not found in {delivery_images}"
            # Verify USPS is NOT in the delivery images
            assert not any(
                coordinator.data.get("image_name") in img for img in delivery_images
            ), f"USPS image should not be in {delivery_images}"
            # Verify the gif path
            assert "generic_deliveries.gif" in gif_path, (
                f"Expected generic_deliveries.gif in path, got {gif_path}"
            )
            return True

        mock_generate_gif.side_effect = mock_generate_gif_func

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

        # Verify generate_delivery_gif was called to create animated GIF
        mock_generate_gif.assert_called_once()


async def test_walmart_camera(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"
        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_walmart_delivery_camera"}
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_walmart_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_walmart.jpg" in caplog.text


async def test_walmart_camera_with_image_data(
    hass,
    mock_imap_walmart_delivered_with_photo,
    integration,
    mock_osremove,
    mock_osmakedir,
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
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "walmart_image": "test_walmart_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
        walmart_camera = None
        for camera in cameras:
            if camera._type == "walmart_camera":
                walmart_camera = camera
                break

        await walmart_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_walmart_delivery_camera")

        # Check that it's using the Walmart image path
        assert "test_walmart_image.jpg" in state.attributes.get("file_path")


async def test_walmart_camera_with_custom_image(
    hass,
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_walmart_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_walmart.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_walmart.jpg" in caplog.text


async def test_walmart_camera_default_image_path(
    hass,
    mock_imap_no_email,
    integration,
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
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"
        # Should use the new Walmart-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_walmart_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
            in state.attributes.get("file_path")
        )


async def test_fedex_camera(
    hass,
    mock_imap_no_email,
    integration,
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
    """Test FedEx camera functionality."""
    entry = integration

    entries = hass.config_entries.async_entries(DOMAIN)

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_fedex_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail FedEx Delivery Camera"
        assert (
            "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_fedex_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
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

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_fedex_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail FedEx Delivery Camera"
        assert "images/test_fedex.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_fedex_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_fedex.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_fedex.jpg" in caplog.text


async def test_fedex_camera_with_image_data(
    hass,
    mock_imap_fedex_delivered_with_photo,
    integration,
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
    """Test FedEx camera with image data."""
    entry = integration

    # Mock coordinator data with FedEx image
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "fedex_image": "test_fedex_image.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        state = hass.states.get("camera.mail_fedex_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail FedEx Delivery Camera"

        # Update the camera to use the new data
        cameras = entry.runtime_data.cameras
        fedex_camera = None
        for camera in cameras:
            if camera._type == "fedex_camera":
                fedex_camera = camera
                break

        await fedex_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_fedex_delivery_camera")

        # Check that it's using the FedEx image path
        assert "test_fedex_image.jpg" in state.attributes.get("file_path")


async def test_fedex_camera_with_custom_image(
    hass,
    mock_imap_no_email,
    integration,
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
    """Test FedEx camera with custom image functionality."""
    # Unload the default config
    entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()

    # Load config with custom FedEx image settings
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_fedex_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail FedEx Delivery Camera"
        assert "images/test_fedex.jpg" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_fedex_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        assert "images/test_fedex.jpg" in state.attributes.get("file_path")
        assert "Custom No Mail: images/test_fedex.jpg" in caplog.text


async def test_fedex_camera_default_image_path(
    hass,
    mock_imap_no_email,
    integration,
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
    """Test FedEx camera uses correct default image path."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
    ):
        state = hass.states.get("camera.mail_fedex_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail FedEx Delivery Camera"
        # Should use the new FedEx-specific default image
        assert (
            "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
            in state.attributes.get("file_path")
        )

        service_data = {"entity_id": "camera.mail_fedex_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()

        assert (
            "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
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

    # Mock config data to use a simpler path for resolution test
    # The FAKE_CONFIG_DATA_CUSTOM_IMG uses "images/test.gif"

    # Mock Path.exists and Path.resolve
    # When resolve is called on "images/test.gif" (file_path) and the custom config path
    # they should match.

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.resolve", side_effect=lambda: Path("/abs/images/test.gif")),
    ):
        # Test the _is_custom_no_mail_image method
        result = camera._is_custom_no_mail_image("usps", "images/test.gif")

        # Should return True for custom no-mail image
        assert result is True


async def test_generic_camera_skip_conditions(hass, caplog):
    """Test that generic camera logs debug messages when skipping images."""
    config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "resources": ["amazon_delivered"],  # Amazon sensor enabled
            "amazon_custom_img": False,
        },
    )

    coordinator = MagicMock()
    coordinator.last_update_success = True

    # Setup data where Amazon has a 'no deliveries' image
    # and NO active deliveries (count is 0 or missing)
    coordinator.data = {
        ATTR_IMAGE_PATH: "custom_components/mail_and_packages/images/",
        ATTR_AMAZON_IMAGE: "no_deliveries_amazon.jpg",
        "amazon_delivered": 0,  # No deliveries
    }

    # Create the generic camera
    camera = MailCam(hass, "generic_camera", config, coordinator)

    # Mock file existence so it attempts to process
    # Use path mock here
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(camera, "check_file_path_access"),
        patch.object(camera, "schedule_update_ha_state"),
    ):
        await camera.update_file_path()

    # Check for the specific debug message from the 'is_no_mail' branch
    assert "Generic camera - filtered out amazon no-mail image" in caplog.text

    # Clear caplog for next check
    caplog.clear()

    # Update data: Valid image, but still 0 deliveries
    coordinator.data[ATTR_AMAZON_IMAGE] = "package_arrived.jpg"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(camera, "check_file_path_access"),
        patch.object(camera, "schedule_update_ha_state"),
    ):
        await camera.update_file_path()

    # Check for the specific debug message from the 'not has_current_deliveries' branch
    assert (
        "Generic camera - filtered out amazon (no current deliveries, count=0)"
        in caplog.text
    )


async def test_camera_fallback_to_recent_file(
    hass,
    mock_imap_no_email,
    integration,
    caplog,
):
    """Test that camera falls back to the most recent file if specific image is missing."""
    entry = integration

    # Setup coordinator data with a file that "doesn't exist"
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "amazon_image": "missing_file.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "amazon_delivered": 1,
    }

    # Mock iterdir to simulate directory contents
    f1 = MagicMock(spec=Path)
    f1.name = "old.jpg"
    f1.__str__.return_value = (
        "custom_components/mail_and_packages/images/amazon/old.jpg"
    )
    f1.exists.return_value = True
    f1.is_file.return_value = True
    f1.stat.return_value.st_mtime = 1000

    f2 = MagicMock(spec=Path)
    f2.name = "new.jpg"
    f2.__str__.return_value = (
        "custom_components/mail_and_packages/images/amazon/new.jpg"
    )
    f2.exists.return_value = True
    f2.is_file.return_value = True
    f2.stat.return_value.st_mtime = 2000

    def mock_path_exists(*args, **kwargs):
        if not args:
            return False
        path = args[0]
        if "missing_file.jpg" in str(path):
            return False
        # The parent directory exists
        if "amazon" in str(path) and "images" in str(path):
            return True
        return False

    with (
        patch("os.path.exists", side_effect=mock_path_exists),
        patch("os.access", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.Path",
            autospec=True,
        ) as mock_path_class,
        patch(
            "custom_components.mail_and_packages.camera.anyio.Path.exists",
            new_callable=AsyncMock,
            side_effect=mock_path_exists,
        ),
    ):
        mock_path_instance = mock_path_class.return_value
        # If Path(path).parent is called, return another mock or self
        mock_path_instance.parent = MagicMock(spec=Path)
        mock_path_instance.parent.__str__.return_value = (
            "custom_components/mail_and_packages/images/amazon"
        )
        mock_path_instance.parent.exists.return_value = True
        mock_path_instance.parent.iterdir.return_value = [f1, f2]
        mock_path_instance.exists.side_effect = mock_path_exists

        # Also mock the Path class call to return different things based on input if needed
        # but for this test, returning mock_path_instance is mostly fine as long as we don't
        # need different behavior for different paths.
        # Actually, Path(__file__) is called.
        # Path(__file__).parent should return a path that exists.

        # Trigger update
        cameras = entry.runtime_data.cameras
        amazon_camera = next(c for c in cameras if c._type == "amazon_camera")

        await amazon_camera.update_file_path()
        await hass.async_block_till_done()

        # Verify it picked the newer file
        state = hass.states.get("camera.mail_amazon_delivery_camera")
        assert "new.jpg" in state.attributes.get("file_path")
        assert "found alternative image file" in caplog.text


@pytest.mark.asyncio
async def test_camera_service_update_specific_explicit(
    hass,
    mock_imap_no_email,
    integration,
):
    """Test updating a specific camera via service with explicit mock check."""
    entry = integration

    # Get the Amazon camera object from hass data
    cameras = entry.runtime_data.cameras
    amazon_cam = next(c for c in cameras if "amazon" in c.entity_id)
    target_entity_id = amazon_cam.entity_id

    # Patch the update_file_path method on the instance to verify it gets called
    with patch.object(amazon_cam, "update_file_path") as mock_update:
        # Call service targeting this specific entity
        await hass.services.async_call(
            DOMAIN,
            "update_image",
            {"entity_id": target_entity_id},
            blocking=True,
        )

        # Verify the update_file_path method was called on the camera instance
        mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_camera_file_not_found(hass, mock_update):
    """Test camera behavior when the expected image file is missing."""
    mock_coordinator = MagicMock()
    mock_config = MagicMock()
    mock_config.data = {"host": "test.host"}

    cam = MailCam(hass, "amazon_camera", mock_config, mock_coordinator)
    cam._file_path = "/nonexistent/path.jpg"

    image = await cam.async_camera_image()
    assert image is None


@pytest.mark.asyncio
async def test_camera_image_read_error(hass, tmp_path):
    """Test camera behavior when failing to read an existing image file."""
    # Create a secure temporary directory and file path
    d = tmp_path / "test_dir"
    d.mkdir()
    safe_file_path = str(d / "test_image.jpg")

    mock_coord = MagicMock()
    mock_config = MagicMock()
    cam = MailCam(hass, "amazon_camera", mock_config, mock_coord)

    # Assign the secure temporary path
    cam._file_path = safe_file_path

    # Simulate file existing but failing to open
    with patch("builtins.open", side_effect=FileNotFoundError):
        image = await cam.async_camera_image()
        assert image is None


@pytest.mark.asyncio
async def test_camera_find_alternative_image_no_dir(hass, caplog):
    """Test _find_alternative_image when directory is missing."""
    cam = MailCam(hass, "ups_camera", MagicMock(), MagicMock())

    with patch("pathlib.Path.exists", return_value=False):
        # Trigger alternative image search
        await cam._find_alternative_image("/fake/path/image.jpg", "image.jpg")
        assert "directory does not exist" in caplog.text


@pytest.mark.asyncio
async def test_camera_service_update_multiple_entities(
    hass,
    mock_imap_no_email,
    integration,
):
    """Test updating multiple specific cameras via service."""
    entry = integration
    cameras = entry.runtime_data.cameras

    # Select two cameras to update
    target_ids = [cameras[0].entity_id, cameras[1].entity_id]

    with patch.object(MailCam, "update_file_path") as mock_update:
        await hass.services.async_call(
            DOMAIN,
            "update_image",
            {ATTR_ENTITY_ID: target_ids},
            blocking=True,
        )

        # Verify both target cameras were updated
        assert mock_update.call_count == 2


@pytest.mark.asyncio
async def test_camera_update_coordinator_failed(
    hass,
    mock_imap_no_email,
    integration,
    caplog,
):
    """Test camera update early exit when the coordinator update state has failed."""
    entry = integration
    cameras = entry.runtime_data.cameras
    target_camera = cameras[0]

    # Simulate a failed update state
    target_camera.coordinator.last_update_success = False

    with patch.object(target_camera, "_update_standard_camera") as mock_update:
        await target_camera.update_file_path()
        # Should return before calling update logic
        mock_update.assert_not_called()
        assert "Update to update camera image. Unavailable." in caplog.text


async def test_is_custom_no_mail_file_not_exists_fixed(
    hass,
    mock_imap_no_email,
    integration,
):
    """Custom path configured but file missing on disk."""
    entry = integration
    camera = entry.runtime_data.cameras[0]

    # Use a fake config object to bypass ConfigEntry data protection
    fake_config = MagicMock()
    fake_config.data = {
        "amazon_custom_img": True,
        "amazon_custom_img_file": "/non/existent/path.jpg",
    }

    with (
        patch.object(camera, "config", fake_config),
        patch(
            "custom_components.mail_and_packages.camera.const.CONF_AMAZON_CUSTOM_IMG",
            "amazon_custom_img",
        ),
        patch(
            "custom_components.mail_and_packages.camera.const.CONF_AMAZON_CUSTOM_IMG_FILE",
            "amazon_custom_img_file",
        ),
        patch("pathlib.Path.exists", return_value=False),
    ):
        result = camera._is_custom_no_mail_image("amazon", "/some/path.jpg")
        assert result is False


async def test_find_alternative_image_oserror_fixed(
    hass,
    mock_imap_no_email,
    integration,
    caplog,
):
    """Handle OSError during directory iteration."""
    entry = integration
    camera = entry.runtime_data.cameras[0]
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.iterdir", side_effect=OSError("Permission Denied")),
    ):
        # Trigger the fallback logic
        await camera._find_alternative_image("/fake/path/img.jpg", "img.jpg")

        # Verify the exception was caught and logged
        assert "error listing directory" in caplog.text


async def test_update_file_path_no_data(hass, mock_imap_no_email, integration, caplog):
    """Early exit when coordinator data is missing."""
    entry = integration
    camera = entry.runtime_data.cameras[0]
    camera.coordinator.data = None

    await camera.update_file_path()
    assert "Unable to update camera image, no data." in caplog.text


async def test_usps_camera_custom_no_mail(hass, mock_imap_no_email, integration):
    """USPS camera using custom no-mail setting."""
    entry = integration
    camera = next(c for c in entry.runtime_data.cameras if c._type == "usps_camera")

    # Force state where no email data is present but custom image is set
    camera.coordinator.data = {}
    camera._no_mail = "custom_none.gif"

    camera._update_usps_camera()
    assert camera._file_path == "custom_none.gif"


async def test_collect_generic_delivery_images_skip_no_attr(
    hass,
    mock_imap_no_email,
    integration,
):
    """Skip cameras with no image attribute mapping."""
    entry = integration
    camera = next(c for c in entry.runtime_data.cameras if c._type == "generic_camera")

    # Patch CAMERA_DATA to include a fake camera that won't have an ATTR in const
    with patch(
        "custom_components.mail_and_packages.camera.CAMERA_DATA",
        {"fake_camera": {"sensor_name": "fake"}},
    ):
        images = camera._collect_generic_delivery_images()
        assert len(images) == 0


async def test_update_standard_camera_no_attr(hass, mock_imap_no_email, integration):
    """Early exit when attribute mapping is missing."""
    entry = integration
    cameras = entry.runtime_data.cameras
    # Use a real camera instance already initialized in CAMERA_DATA
    camera = next(c for c in cameras if c._type == "amazon_camera")

    # Patch getattr so that it fails to find the image attribute constant
    with patch("custom_components.mail_and_packages.camera.getattr", return_value=None):
        await camera._update_standard_camera()
        # Ensure the default 'no deliveries' path remains set
        assert "no_deliveries_amazon.jpg" in camera._file_path


async def test_get_sensor_name_usps(hass, mock_imap_no_email, integration):
    """Correct sensor mapping for USPS."""
    entry = integration
    camera = entry.runtime_data.cameras[0]
    name = camera._get_sensor_name_for_camera("usps_camera")
    assert name == "usps_mail"


async def test_handle_coordinator_update_logic(
    hass,
    mock_imap_no_email,
    integration,
    caplog,
):
    """Handle incoming coordinator data updates."""
    entry = integration
    camera = entry.runtime_data.cameras[0]

    # Directly trigger the update handler
    camera._handle_coordinator_update()
    assert "coordinator update received" in caplog.text


async def test_usps_camera_with_image_data_full(hass, mock_imap_no_email, integration):
    """Test USPS camera behavior with valid image data present in coordinator."""
    entry = integration
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "usps_image": "test_usps.gif",
        "image_path": "images/usps/",
    }

    camera = next(c for c in entry.runtime_data.cameras if c._type == "usps_camera")
    await camera.update_file_path()

    assert "images/usps/test_usps.gif" in camera.extra_state_attributes["file_path"]


async def test_camera_is_custom_no_mail_image(hass, mock_imap_no_email, integration):
    """Test _is_custom_no_mail_image helper."""
    entry = integration
    camera = entry.runtime_data.cameras[0]

    # Test USPS case
    with (
        patch(
            "custom_components.mail_and_packages.camera.const.CONF_CUSTOM_IMG",
            "custom_img",
        ),
        patch(
            "custom_components.mail_and_packages.camera.const.CONF_CUSTOM_IMG_FILE",
            "custom_img_file",
        ),
        patch.object(
            camera,
            "config",
            new=MagicMock(data={"custom_img": True, "custom_img_file": "custom.gif"}),
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        assert camera._is_custom_no_mail_image("usps", "custom.gif") is True


async def test_get_sensor_name_for_camera(hass, mock_imap_no_email, integration):
    """Test _get_sensor_name_for_camera helper."""
    entry = integration
    camera = entry.runtime_data.cameras[0]

    assert camera._get_sensor_name_for_camera("amazon_camera") == "amazon_delivered"
    assert camera._get_sensor_name_for_camera("usps_camera") == "usps_mail"


async def test_generic_camera_gif_failure_fallback(
    hass,
    integration,
    caplog,
):
    """Test Generic camera fallback to a static delivery image when GIF generation fails."""
    entry = integration
    coordinator = entry.runtime_data.coordinator
    coordinator.data = {
        "amazon_image": "test_amazon_delivery.jpg",
        "image_path": "custom_components/mail_and_packages/images/",
        "amazon_delivered": 1,
    }

    with (
        patch("os.path.exists", return_value=True),
        patch("os.access", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.camera.resize_images",
            return_value=["/fake/path/amazon/res1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.camera.generate_delivery_gif",
            return_value=False,
        ),
    ):
        cameras = entry.runtime_data.cameras
        generic_camera = next(c for c in cameras if c._type == "generic_camera")

        await generic_camera.update_file_path()
        await hass.async_block_till_done()

        assert "Failed to create animated GIF" in caplog.text
        assert "amazon" in str(generic_camera._file_path) or "mail_none.gif" in str(
            generic_camera._file_path
        )
