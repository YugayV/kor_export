Add-Type -AssemblyName System.Runtime.WindowsRuntime
function Convert-ImageToText($path) {
  $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($path).AsTask().GetAwaiter().GetResult()
  $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).AsTask().GetAwaiter().GetResult()
  $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).AsTask().GetAwaiter().GetResult()
  $bmp = $decoder.GetSoftwareBitmapAsync().AsTask().GetAwaiter().GetResult()
  $ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  $result = $ocr.RecognizeAsync($bmp).AsTask().GetAwaiter().GetResult()
  $result.Text
}
$paths = @(
  'c:\Users\User\Documents\kor_export\Screenshot 2026-06-18 222316.png',
  'c:\Users\User\Documents\kor_export\Screenshot 2026-06-18 222324.png',
  'c:\Users\User\Documents\kor_export\Screenshot 2026-06-18 222329.png'
)
foreach ($p in $paths) {
  Write-Output "=== $p ==="
  Convert-ImageToText $p
}
