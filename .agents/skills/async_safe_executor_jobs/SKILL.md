---
name: Async-Safe I/O & Executor Guidelines
description: Best practices for performing non-blocking file, image, and network I/O operations inside Home Assistant's async loop.
---

# Async-Safe I/O & Executor Guidelines

This skill defines the threading and asynchronous safety rules to follow when interacting with the filesystem or network within the Home Assistant async loop.

## Guidelines

### 1. No Blocking I/O in the Event Loop
* Do not call blocking synchronous functions (like `os.path.exists`, `shutil.copyfile`, or standard file `open()`) directly in async contexts (such as sensor/camera updates or setup methods). Doing so blocks the Home Assistant main thread, degrading system performance.

### 2. Utilizing `async_add_executor_job`
* Wrap synchronous operations that must run inside the main thread in an executor job:
  ```python
  await self.hass.async_add_executor_job(copyfile, str(src), str(dst))
  ```

### 3. Asynchronous Alternatives
* Prefer async file/directory utilities from libraries like `anyio` or standard library wrappers where applicable. For example:
  ```python
  import anyio
  if not await anyio.Path(path_str).exists():
      # async-safe path checking
  ```
