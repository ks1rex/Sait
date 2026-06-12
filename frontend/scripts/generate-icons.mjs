import sharp from 'sharp'
import pngToIco from 'png-to-ico'
import { writeFileSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const publicDir = join(__dirname, '..', 'public')
const src = join(publicDir, 'logo-source.png')

const PNG_SIZES = [
  ['favicon-16x16.png',    16],
  ['favicon-32x32.png',    32],
  ['favicon-48x48.png',    48],
  ['apple-touch-icon.png', 180],
  ['logo-192.png',         192],
  ['logo-512.png',         512],
]

async function main() {
  for (const [name, size] of PNG_SIZES) {
    await sharp(src).resize(size, size).png().toFile(join(publicDir, name))
    console.log(`  ✓ ${name}`)
  }

  // favicon.ico — embed 16, 32, 48 layers
  const icoBuffers = await Promise.all(
    [16, 32, 48].map(size => sharp(src).resize(size, size).png().toBuffer())
  )
  const icoData = await pngToIco(icoBuffers)
  writeFileSync(join(publicDir, 'favicon.ico'), icoData)
  console.log('  ✓ favicon.ico  (16/32/48 px)')
}

main().catch(err => { console.error(err); process.exit(1) })
