# QO-100 Emergency Communication Terminal

Taşınabilir, şebekeden bağımsız çalışan bir GEO uydu haberleşme terminali. PlutoSDR ve GNU Radio Companion üzerinde geliştirilmiştir. Test platformu olarak QO-100 (Es'hail-2) dar bant transponderi kullanılmaktadır. TÜBİTAK 2209-B kapsamında desteklenen bir lisans bitirme projesidir.

## Özellikler

- PlutoSDR üzerinden eşzamanlı SSB/AM ses ve QPSK veri kanalı
- Reed-Solomon (255,223) FEC ile korumalı veri iletimi
- QO-100 BPSK beacon'ına Costas Loop ile kilitlenen RX frekans senkronizasyonu
- FFT/NCO tabanlı yazılımsal TX frekans senkronizasyonu
- FDMA/TDMA çoklu erişim mimarisi ve üç katmanlı Python GUI
- gr-satellites tabanlı QO-100 multimedia beacon (8APSK) çözümleme desteği

## Repo Yapısı

```
grc/     GNU Radio Companion flowgraph ve hier blokları (modem zinciri, senkronizasyon, GUI)
tools/   Metin sohbet / burst iletim aracı ve ilgili yardımcı kodlar (bkz. tools/README.md)
```

Kod detayları ve kullanım şekli için `tools/` klasöründeki kendi README dosyasına bakınız.

## Gereksinimler

- GNU Radio 3.10+
- [gr-satellites](https://github.com/daniestevez/gr-satellites) (kurulu olmalı — multimedia beacon çözümleme ve bazı yardımcı bloklar için gereklidir)
- Python `reedsolo` paketi (kurulu olmalı — Reed-Solomon FEC kodlama/çözme için gereklidir)

  ```
  pip install reedsolo
  ```

- PlutoSDR ve ilgili sürücüler (libiio / libad9361 / gr-iio)

## Kullanım

1. `grc/` altındaki flowgraph'ı GNU Radio Companion ile açıp derleyin.
2. `tools/` altındaki araç ile metin/burst iletimini başlatın (ayrıntılar için `tools/README.md`).

## Örnek Kayıt

Test/örnek IQ kaydı yakında eklenecektir.

## Lisans

GPL v3
