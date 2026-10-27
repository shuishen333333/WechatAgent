"""Resolve one authorized image locally using unchanged weflow-cli codecs."""
import base64
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Embedded Python uses an isolated _pth file and does not add the script directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / 'components' / 'weflow-cli' / 'scripts'))
try:
    import wechat_media as media
    from wechat_sticker import resolve_sticker
    from PIL import Image, ImageOps, UnidentifiedImageError
    import subprocess
    spec = importlib.util.spec_from_file_location('reader_api_image', ROOT / 'scripts' / 'reader-api.py')
    reader_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader_api)
except (ImportError, OSError) as error:
    if __name__ != '__main__':
        raise
    code = 'IMAGE_DEPENDENCY_MISSING' if isinstance(error, ModuleNotFoundError) else 'IMAGE_DEPENDENCY_LOAD_FAILED'
    result = {'success': False, 'error': code, 'exceptionType': type(error).__name__}
    name = getattr(error, 'name', '') or ''
    if re.fullmatch(r'[A-Za-z0-9_.]{1,80}', name):
        result['module'] = name
    print(json.dumps(result), file=sys.stderr)
    sys.exit(1)


from wechat_image_normalize import normalize_image


# Below this longest side the only local copy is WeChat's preview thumbnail.
THUMBNAIL_MAX_SIDE = 256
# Pictures sent as WeChat *files* keep their original bytes on disk, but only
# once the desktop client has downloaded the file itself.
MAX_IMAGE_FILE_BYTES = 20 * 1024 * 1024
SAFE_FILE_NAME = re.compile(r'^[^\\/:*?"<>|\x00-\x1f\x7f]{1,180}$')


def resolve_file_image(descriptor, account):
    """Read an image that arrived as a WeChat file message (no encryption, no thumb)."""
    name = descriptor.get('name') or ''
    size = descriptor.get('size')
    md5 = (descriptor.get('md5') or '').lower()
    if not SAFE_FILE_NAME.fullmatch(name) or name != os.path.basename(name):
        raise RuntimeError('IMAGE_FILE_DESCRIPTOR_INVALID')
    if not isinstance(size, int) or not 0 < size <= MAX_IMAGE_FILE_BYTES:
        raise RuntimeError('IMAGE_FILE_DESCRIPTOR_INVALID')
    if md5 and not re.fullmatch(r'[a-f0-9]{32}', md5):
        raise RuntimeError('IMAGE_FILE_DESCRIPTOR_INVALID')
    deadline = time.monotonic() + 3
    visited = 0
    for folder in (account / 'msg' / 'file', account / 'FileStorage' / 'File'):
        if not folder.is_dir():
            continue
        stack = [(folder, 0)]
        while stack and visited < 4000 and time.monotonic() < deadline:
            current, depth = stack.pop()
            try:
                entries = list(os.scandir(current))
            except OSError:
                continue
            for entry in entries:
                visited += 1
                if visited > 4000 or time.monotonic() >= deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if depth < 4:
                            stack.append((pathlib.Path(entry.path), depth + 1))
                        continue
                    if entry.name.casefold() != name.casefold():
                        continue
                    if entry.stat().st_size != size:
                        continue
                    with open(entry.path, 'rb') as stream:
                        raw = stream.read(MAX_IMAGE_FILE_BYTES + 1)
                except OSError:
                    continue
                if len(raw) != size:
                    continue
                if md5 and hashlib.md5(raw).hexdigest() != md5:
                    continue
                if pathlib.Path(entry.path).suffix.casefold() in ('.heic', '.heif'):
                    raw = transcode_heic(entry.path) or raw
                return normalize_image(raw)
    raise RuntimeError('IMAGE_FILE_NOT_DOWNLOADED')


# iPhones hand over HEIC, which Pillow cannot decode without an extra wheel.
# Windows already ships an HEIF decoder, so reuse it through WIC instead.
HEIC_SCRIPT = r'''
param([string]$In,[string]$Out,[int]$MaxSide)
Add-Type -AssemblyName PresentationCore | Out-Null
$dec = [System.Windows.Media.Imaging.BitmapDecoder]::Create([Uri]$In, 'None', 'OnLoad')
$frame = $dec.Frames[0]
$scale = 1.0
if($frame.PixelWidth -gt $MaxSide){ $scale = $MaxSide / $frame.PixelWidth }
$target = $frame
if($scale -lt 1.0){
  $xf = New-Object System.Windows.Media.ScaleTransform($scale, $scale)
  $target = New-Object System.Windows.Media.Imaging.TransformedBitmap($frame, $xf)
}
$enc = New-Object System.Windows.Media.Imaging.JpegBitmapEncoder
$enc.QualityLevel = 90
$enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($target))
$stream = [System.IO.File]::Create($Out)
try { $enc.Save($stream) } finally { $stream.Close() }
'''


def transcode_heic(path, max_side=1600):
    """Convert one HEIC/HEIF file to JPEG bytes via the Windows imaging codec."""
    script = pathlib.Path(tempfile.gettempdir()) / 'wechatagent-heic.ps1'
    output = pathlib.Path(tempfile.gettempdir()) / ('wechatagent-heic-%d.jpg' % os.getpid())
    try:
        script.write_text(HEIC_SCRIPT, encoding='utf-8')
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', str(script), '-In', str(path), '-Out', str(output), '-MaxSide', str(max_side)],
            capture_output=True, timeout=25, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if output.is_file() and output.stat().st_size > 0:
            return output.read_bytes()
        return None
    except Exception:
        return None
    finally:
        try:
            output.unlink()
        except OSError:
            pass


def resolve(descriptor):
    reader = reader_api.Reader(ROOT, metadata_readonly=True)
    talker = descriptor['talker']
    if not reader.image_talker_allowed(talker):
        raise RuntimeError('IMAGE_CONVERSATION_NOT_ALLOWED')
    if descriptor.get('kind') == 'file-image':
        return resolve_file_image(descriptor, reader.account)
    row = reader.image_row(talker, descriptor)
    content = row['imageXml']
    if row['localType'] == 47:
        project = reader_api.read_json(ROOT / 'config' / 'wechatagent.json')
        return resolve_sticker(reader.account, content, normalize_image,
            allow_cdn=project.get('wechat', {}).get('media', {}).get('allowStickerCdn', False) is True,
            allow_cdn_alias=project.get('wechat', {}).get('media', {}).get('allowStickerCdnAlias', False) is True)
    resource = reader.account / 'db_storage' / 'message' / 'message_resource.db'
    ids = list(media.extract_media_md5s(content))
    if resource.is_file():
        connection = None
        try:
            key, salt = reader_api.nt.derive_database_key(str(resource), '', '', reader.passphrase)
            connection, cursor = reader_api.nt.connect_nt_db(str(resource), key, salt)
            cursor.execute('PRAGMA query_only=ON')
            if int(descriptor['serverId'] or 0):
                cursor.execute('SELECT packed_info FROM MessageResourceInfo WHERE message_svr_id=? AND message_local_id=? AND message_create_time=? LIMIT 8', (int(descriptor['serverId']), descriptor['localId'], descriptor['createTime']))
                for (packed,) in cursor.fetchall():
                    ids.extend(media.extract_blob_md5s(packed))
        except Exception:
            pass  # Exact cache identity remains available; never guess another image.
        finally:
            if connection is not None:
                connection.close()
    ids = list(dict.fromkeys(value.lower() for value in ids if re.fullmatch(r'[a-fA-F0-9]{32}', value)))
    settings = reader_api.read_json(reader.settings_file)
    keys = []
    try:
        saved = reader_api.local_secret(str(settings.get('imageAesKey') or ''))
        aes = bytes.fromhex(saved) if re.fullmatch(r'[a-fA-F0-9]{32}', saved) else saved.encode('ascii')
        xor = int(reader_api.local_secret(str(settings.get('imageXorKey') or '0')), 0) & 255
        if len(aes) == 16:
            keys.append((xor, aes))
    except Exception:
        pass
    derived = media.resolve_v2_media_key(str(reader.account), reader.own_wxid)
    if derived and derived not in keys:
        keys.append(derived)
    attach = reader.account / 'msg' / 'attach' / hashlib.md5(talker.encode()).hexdigest()
    # Resource IDs bind files to the exact server message. Local IDs alone are
    # deliberately insufficient because they collide between shards/chats.
    # Highest fidelity first: WeChat keeps *_h.dat (original) only when the full
    # image was downloaded; .dat is the compressed copy and _t.dat the thumbnail.
    order = ('_h.dat', '.dat', '_t.dat')
    best = None
    for file_id in ids:
        candidates = []
        if attach.is_dir():
            for month in sorted(attach.iterdir(), reverse=True):
                image_dir = month / 'Img'
                for suffix in order:
                    file = image_dir / (file_id + suffix)
                    if file.is_file() and file.stat().st_size <= media.MAX_EMBED_SIZE:
                        candidates.append((order.index(suffix), file))
        candidates.sort(key=lambda item: item[0])
        for _, file in candidates:
            for xor, aes in keys:
                decoded = media.decode_wechat_v2(str(file), xor, aes)
                if not decoded:
                    continue
                try:
                    payload = normalize_image(decoded[0])
                except Exception:
                    continue
                area = int(payload.get('width') or 0) * int(payload.get('height') or 0)
                if best is None or area > best[0]:
                    best = (area, payload)
                break
    if best is not None:
        width, height = int(best[1].get('width') or 0), int(best[1].get('height') or 0)
        # A thumbnail alone is not the picture the sender meant; report it
        # instead of handing the model an unreadable 100px preview.
        if max(width, height) < THUMBNAIL_MAX_SIDE:
            raise RuntimeError('IMAGE_ONLY_THUMBNAIL')
        return best[1]
    raise RuntimeError('IMAGE_LOCAL_COPY_UNAVAILABLE')


def image_error_code(error):
    if isinstance(error, RuntimeError) and re.fullmatch(r'IMAGE_[A-Z_]{3,80}', str(error)):
        return str(error)
    if isinstance(error, RuntimeError) and str(error) == 'NORMALIZED_IMAGE_TOO_LARGE':
        return 'IMAGE_NORMALIZED_TOO_LARGE'
    if isinstance(error, (UnidentifiedImageError, EOFError)):
        return 'IMAGE_FORMAT_UNSUPPORTED'
    if isinstance(error, PermissionError):
        return 'IMAGE_FILE_ACCESS_DENIED'
    if isinstance(error, FileNotFoundError):
        return 'IMAGE_LOCAL_FILE_MISSING'
    if isinstance(error, subprocess.TimeoutExpired):
        return 'IMAGE_DECODE_TIMEOUT'
    if isinstance(error, (MemoryError, Image.DecompressionBombError)):
        return 'IMAGE_PIXEL_LIMIT'
    if isinstance(error, (json.JSONDecodeError, KeyError, TypeError)):
        return 'IMAGE_DESCRIPTOR_INVALID'
    return 'IMAGE_RESOLUTION_FAILED'


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--check-runtime']:
            print(json.dumps({'success': True, 'imageWorkerReady': True}))
        else:
            descriptor = json.loads(sys.stdin.read(16384))
            print(json.dumps({'success': True, **resolve(descriptor)}))
    except Exception as error:
        print(json.dumps({'success': False, 'error': image_error_code(error),
                         'exceptionType': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
