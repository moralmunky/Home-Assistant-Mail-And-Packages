"""Tests for camera component."""

from unittest.mock import MagicMock, mock_open, patch

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
        "camera.mail_walmart_delivery_camera",
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
        "camera.mail_walmart_delivery_camera",
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

        generic_camera.update_file_path()
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

        generic_camera.update_file_path()
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

        generic_camera.update_file_path()
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
    """Test Generic camera with USPS delivery images using manual coordinator data."""
    entry = integration

    # Mock coordinator data with USPS delivery image
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        "image_name": "test_usps_delivery.gif",
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

        generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Check that it's using the USPS delivery image
        assert "test_usps_delivery.gif" in state.attributes.get("file_path")


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
    """Test Generic camera with all delivery types (Amazon, UPS, USPS, Walmart) to create animated GIF."""
    entry = integration

    # Mock coordinator data with all delivery types
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.data = {
        # Amazon delivery
        "amazon_image": "test_amazon_delivery.jpg",
        # UPS delivery  
        "ups_image": "test_ups_delivery.jpg",
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        # Walmart delivery
        "walmart_image": "test_walmart_delivery.jpg",
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch("PIL.Image.open") as mock_pil_open, patch("PIL.Image.save") as mock_pil_save:
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

        generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with all 4 delivery images
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert "Generic camera - created animated GIF with 4 delivery images" in caplog.text
        
        # Verify PIL was called to create animated GIF
        mock_pil_save.assert_called_once()


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
        # UPS - no mail image (should be filtered out)
        "ups_image": "no_deliveries_ups.jpg",
        # USPS - no mail image (should be filtered out)
        "image_name": "mail_none.gif",
        # Walmart - actual delivery
        "walmart_image": "test_walmart_delivery.jpg",
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch("PIL.Image.open") as mock_pil_open, patch("PIL.Image.save") as mock_pil_save:
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

        generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with only 2 actual delivery images (Amazon and Walmart)
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert "Generic camera - created animated GIF with 2 delivery images" in caplog.text
        
        # Verify PIL was called to create animated GIF
        mock_pil_save.assert_called_once()


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
        # UPS delivery  
        "ups_image": "test_ups_delivery.jpg",
        # USPS delivery
        "image_name": "test_usps_delivery.gif",
        # Walmart delivery
        "walmart_image": "test_walmart_delivery.jpg",
        # Common path
        "image_path": "custom_components/mail_and_packages/images/",
    }

    # Mock config to only enable Amazon and Walmart sensors
    entry.data = entry.data.copy()
    entry.data["resources"] = ["amazon_delivered", "walmart_delivered"]  # Only Amazon and Walmart enabled

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch("PIL.Image.open") as mock_pil_open, patch("PIL.Image.save") as mock_pil_save:
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

        generic_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_generic_delivery_camera")

        # Should create animated GIF with only 2 delivery images (Amazon and Walmart)
        # UPS and USPS should be skipped because their sensors are not enabled
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert "Generic camera - created animated GIF with 2 delivery images" in caplog.text
        assert "Generic camera - skipping ups (sensor ups_delivered not enabled)" in caplog.text
        assert "Generic camera - skipping usps (sensor usps_mail not enabled)" in caplog.text
        
        # Verify PIL was called to create animated GIF
        mock_pil_save.assert_called_once()


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
    mock_imap_usps_delivered,
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
    """Test Generic camera with USPS delivery images."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True):
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"
        
        # Should use USPS delivery image since it's the only delivery found
        assert "images/test_usps.gif" in state.attributes.get("file_path")

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        
        assert "images/test_usps.gif" in state.attributes.get("file_path")
        assert "Generic camera - found USPS delivery" in caplog.text


async def test_generic_camera_with_multiple_delivery_images(
    hass,
    integration,
    mock_imap_amazon_delivered,
    mock_imap_ups_delivered_with_photo,
    mock_imap_usps_delivered,
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
    """Test Generic camera with multiple delivery images (Amazon, UPS, USPS)."""
    entry = integration

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
    ), patch("os.path.exists", return_value=True), patch("PIL.Image.open") as mock_pil_open, patch("PIL.Image.save") as mock_pil_save:
        # Mock PIL Image objects
        mock_image = MagicMock()
        mock_pil_open.return_value = mock_image
        
        state = hass.states.get("camera.mail_generic_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Generic Delivery Camera"

        service_data = {"entity_id": "camera.mail_generic_delivery_camera"}
        await hass.services.async_call(DOMAIN, "update_image", service_data)
        await hass.async_block_till_done()
        
        # Should create animated GIF with multiple delivery images
        assert "generic_deliveries.gif" in state.attributes.get("file_path")
        assert "Generic camera - created animated GIF with" in caplog.text
        assert "3 delivery images" in caplog.text
        
        # Verify PIL was called to create animated GIF
        mock_pil_save.assert_called_once()


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

    with patch("os.path.isfile", return_value=True), patch(
        "os.access", return_value=True
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
        state = hass.states.get("camera.mail_walmart_delivery_camera")
        assert state.attributes.get("friendly_name") == "Mail Walmart Delivery Camera"

        # Update the camera to use the new data
        cameras = hass.data[DOMAIN][entry.entry_id][CAMERA]
        walmart_camera = None
        for camera in cameras:
            if camera._type == "walmart_camera":
                walmart_camera = camera
                break

        walmart_camera.update_file_path()
        await hass.async_block_till_done()

        # Get the updated state after the file path update
        state = hass.states.get("camera.mail_walmart_delivery_camera")

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
