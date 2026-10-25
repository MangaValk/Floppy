# Static and bootstrap stage observations

| Sample | Python stage | Body wall s | Lifetime CPU s | Peak RSS KiB | Logical read bytes | Block read bytes | Block write bytes |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | collectstatic | 4.937772 | 4.289795 | 98140 | 23464905 | 176128 | 4096 |
| baseline-large-unverified-cold-0 | resource_env | 1.071619 | 0.971814 | 33708 | 6194733 | 49152 | 0 |
| baseline-large-unverified-cold-0 | sizing_report | 1.003991 | 0.905145 | 33588 | 6194733 | 4096 | 4096 |
| baseline-large-unverified-cold-1 | collectstatic | 5.864258 | 4.045185 | 97596 | 23464944 | 23883776 | 4096 |
| baseline-large-unverified-cold-1 | resource_env | 0.930573 | 1.119424 | 33860 | 6194756 | 0 | 0 |
| baseline-large-unverified-cold-1 | sizing_report | 0.939614 | 0.946985 | 33884 | 6194756 | 0 | 4096 |
| baseline-large-unverified-cold-2 | collectstatic | 4.287545 | 3.204479 | 97716 | 23464953 | 21360640 | 4096 |
| baseline-large-unverified-cold-2 | resource_env | 0.690240 | 0.679836 | 33248 | 6194756 | 5611520 | 0 |
| baseline-large-unverified-cold-2 | sizing_report | 0.280739 | 0.304636 | 33788 | 6194756 | 0 | 4096 |
| baseline-large-verified-cold-0 | collectstatic | 3.513914 | 2.385902 | 97760 | 23464953 | 27439104 | 4096 |
| baseline-large-verified-cold-0 | resource_env | 0.377204 | 0.473398 | 33976 | 6194756 | 0 | 0 |
| baseline-large-verified-cold-0 | sizing_report | 0.384319 | 0.424626 | 33844 | 6194756 | 0 | 4096 |
| baseline-large-verified-cold-1 | collectstatic | 3.480346 | 2.298948 | 97652 | 23464953 | 27430912 | 4096 |
| baseline-large-verified-cold-1 | resource_env | 0.657228 | 0.523194 | 33228 | 6194756 | 5660672 | 0 |
| baseline-large-verified-cold-1 | sizing_report | 0.984042 | 0.853207 | 33396 | 6194756 | 8867840 | 4096 |
| baseline-large-verified-cold-2 | collectstatic | 7.005795 | 4.315672 | 97836 | 23464955 | 16871424 | 4096 |
| baseline-large-verified-cold-2 | resource_env | 0.782790 | 0.972868 | 33776 | 6194756 | 0 | 0 |
| baseline-large-verified-cold-2 | sizing_report | 1.316696 | 0.968540 | 34056 | 6194756 | 0 | 4096 |
| baseline-small-unverified-cold-0 | collectstatic | 2.123020 | 2.031347 | 98164 | 23464821 | 6107136 | 4096 |
| baseline-small-unverified-cold-0 | resource_env | 0.265920 | 0.303777 | 34332 | 6194657 | 0 | 0 |
| baseline-small-unverified-cold-0 | sizing_report | 0.216537 | 0.288258 | 34248 | 6194657 | 0 | 4096 |
| baseline-small-unverified-cold-1 | collectstatic | 2.155871 | 2.175346 | 98448 | 23464821 | 167936 | 4096 |
| baseline-small-unverified-cold-1 | resource_env | 0.242314 | 0.287446 | 34100 | 6194657 | 0 | 0 |
| baseline-small-unverified-cold-1 | sizing_report | 0.338163 | 0.387145 | 34460 | 6194657 | 0 | 4096 |
| baseline-small-unverified-cold-2 | collectstatic | 2.271061 | 2.147531 | 98036 | 23464824 | 94208 | 4096 |
| baseline-small-unverified-cold-2 | resource_env | 0.377020 | 0.391263 | 34272 | 6194657 | 0 | 0 |
| baseline-small-unverified-cold-2 | sizing_report | 0.231989 | 0.282529 | 34080 | 6194657 | 0 | 4096 |
| baseline-small-verified-cold-0 | collectstatic | 5.043085 | 3.293527 | 98032 | 23464823 | 20443136 | 4096 |
| baseline-small-verified-cold-0 | resource_env | 1.118111 | 0.765891 | 33808 | 6194657 | 7348224 | 0 |
| baseline-small-verified-cold-0 | sizing_report | 0.430718 | 0.507887 | 34124 | 6194657 | 0 | 4096 |
| baseline-small-verified-cold-1 | collectstatic | 12.422164 | 5.619409 | 98024 | 23464823 | 19615744 | 4096 |
| baseline-small-verified-cold-1 | resource_env | 1.126625 | 1.010060 | 34132 | 6194657 | 0 | 0 |
| baseline-small-verified-cold-1 | sizing_report | 0.610893 | 0.632566 | 34028 | 6194657 | 0 | 4096 |
| baseline-small-verified-cold-2 | collectstatic | 7.249827 | 3.908797 | 98012 | 23464824 | 17223680 | 4096 |
| baseline-small-verified-cold-2 | resource_env | 0.697405 | 0.737932 | 33900 | 6194657 | 0 | 0 |
| baseline-small-verified-cold-2 | sizing_report | 0.676636 | 0.712553 | 34312 | 6194657 | 0 | 4096 |
| baseline-small-verified-warm-0 | collectstatic | 1.657132 | 1.490112 | 98344 | 23464965 | 10817536 | 4096 |
| baseline-small-verified-warm-0 | resource_env | 0.195553 | 0.224711 | 34084 | 6194756 | 0 | 0 |
| baseline-small-verified-warm-0 | sizing_report | 0.174839 | 0.206875 | 34104 | 6194756 | 0 | 4096 |
| baseline-small-verified-warm-1 | collectstatic | 4.007378 | 2.722248 | 98128 | 23464971 | 13451264 | 4096 |
| baseline-small-verified-warm-1 | resource_env | 0.377799 | 0.423763 | 33972 | 6194756 | 0 | 0 |
| baseline-small-verified-warm-1 | sizing_report | 0.326919 | 0.391494 | 33904 | 6194756 | 0 | 4096 |
| baseline-small-verified-warm-2 | collectstatic | 3.276279 | 2.381546 | 97732 | 23464967 | 15372288 | 4096 |
| baseline-small-verified-warm-2 | resource_env | 0.631323 | 0.574535 | 34140 | 6194756 | 2068480 | 0 |
| baseline-small-verified-warm-2 | sizing_report | 0.315703 | 0.378340 | 34084 | 6194756 | 0 | 4096 |
| baseline-small-verified-warm-3 | collectstatic | 4.245453 | 2.881962 | 98216 | 23464968 | 958464 | 4096 |
| baseline-small-verified-warm-3 | resource_env | 0.516461 | 0.596652 | 34084 | 6194756 | 0 | 0 |
| baseline-small-verified-warm-3 | sizing_report | 0.302188 | 0.354040 | 34088 | 6194756 | 0 | 4096 |
| baseline-small-verified-warm-4 | collectstatic | 3.807237 | 2.295046 | 98068 | 23464971 | 7028736 | 4096 |
| baseline-small-verified-warm-4 | resource_env | 0.317695 | 0.408108 | 33908 | 6194756 | 0 | 0 |
| baseline-small-verified-warm-4 | sizing_report | 0.967999 | 0.899746 | 33652 | 6194756 | 0 | 4096 |
| baseline-small-verified-warm-5 | collectstatic | 3.306083 | 2.437729 | 98132 | 23464968 | 10756096 | 4096 |
| baseline-small-verified-warm-5 | resource_env | 0.494095 | 0.506357 | 33952 | 6194756 | 1048576 | 0 |
| baseline-small-verified-warm-5 | sizing_report | 0.455523 | 0.499450 | 33532 | 6194756 | 0 | 4096 |
| changed-custom-uid-small-verified-cold-0 | static_check | 0.367638 | 0.242753 | 15484 | 992554 | 389120 | 0 |
| changed-custom-uid-small-verified-cold-0 | resource_env | 0.527156 | 0.720493 | 33948 | 6194756 | 0 | 0 |
| changed-custom-uid-small-verified-cold-0 | sizing_report | 0.358471 | 0.407629 | 34124 | 6194756 | 0 | 4096 |
| changed-large-unverified-cold-0 | static_check | 0.758920 | 0.511785 | 15332 | 992554 | 507904 | 0 |
| changed-large-unverified-cold-0 | resource_env | 1.200352 | 0.790312 | 33656 | 6194756 | 4980736 | 0 |
| changed-large-unverified-cold-0 | sizing_report | 0.305423 | 0.364852 | 34176 | 6194756 | 0 | 4096 |
| changed-large-unverified-cold-1 | static_check | 0.196418 | 0.198124 | 14956 | 992554 | 3141632 | 0 |
| changed-large-unverified-cold-1 | resource_env | 0.510696 | 0.421699 | 33188 | 6194756 | 6619136 | 0 |
| changed-large-unverified-cold-1 | sizing_report | 0.224252 | 0.262316 | 34068 | 6194756 | 0 | 4096 |
| changed-large-unverified-cold-2 | static_check | 0.077913 | 0.123991 | 15444 | 992554 | 3047424 | 0 |
| changed-large-unverified-cold-2 | resource_env | 0.351009 | 0.308582 | 33828 | 6194756 | 5705728 | 0 |
| changed-large-unverified-cold-2 | sizing_report | 0.219779 | 0.261453 | 34132 | 6194756 | 0 | 4096 |
| changed-large-verified-cold-0 | static_check | 0.346370 | 0.652059 | 15272 | 992554 | 385024 | 0 |
| changed-large-verified-cold-0 | resource_env | 0.564731 | 0.640951 | 34040 | 6194756 | 24576 | 0 |
| changed-large-verified-cold-0 | sizing_report | 0.385437 | 0.460087 | 34240 | 6194756 | 0 | 4096 |
| changed-large-verified-cold-1 | static_check | 0.148710 | 0.197136 | 15152 | 992554 | 487424 | 0 |
| changed-large-verified-cold-1 | resource_env | 0.418992 | 0.362505 | 33232 | 6194756 | 5357568 | 0 |
| changed-large-verified-cold-1 | sizing_report | 0.203469 | 0.244814 | 33760 | 6194756 | 0 | 4096 |
| changed-large-verified-cold-2 | static_check | 0.101505 | 0.160168 | 15496 | 992554 | 3989504 | 0 |
| changed-large-verified-cold-2 | resource_env | 0.461683 | 0.401749 | 33388 | 6194756 | 7081984 | 0 |
| changed-large-verified-cold-2 | sizing_report | 0.239706 | 0.276670 | 34052 | 6194756 | 200704 | 4096 |
| changed-small-unverified-cold-0 | static_check | 0.234663 | 0.206922 | 15468 | 992554 | 147456 | 0 |
| changed-small-unverified-cold-0 | resource_env | 0.685689 | 0.708515 | 34160 | 6194756 | 0 | 0 |
| changed-small-unverified-cold-0 | sizing_report | 0.358349 | 0.381330 | 34384 | 6194756 | 0 | 4096 |
| changed-small-unverified-cold-1 | static_check | 0.217791 | 0.242090 | 15456 | 992554 | 331776 | 0 |
| changed-small-unverified-cold-1 | resource_env | 0.483836 | 0.484078 | 33788 | 6194756 | 1421312 | 0 |
| changed-small-unverified-cold-1 | sizing_report | 0.679532 | 0.682028 | 34300 | 6194756 | 0 | 4096 |
| changed-small-unverified-cold-2 | static_check | 0.115590 | 0.161526 | 15268 | 992554 | 442368 | 0 |
| changed-small-unverified-cold-2 | resource_env | 0.418616 | 0.380414 | 33992 | 6194756 | 2416640 | 0 |
| changed-small-unverified-cold-2 | sizing_report | 0.316961 | 0.341225 | 34236 | 6194756 | 0 | 4096 |
| changed-small-verified-cold-0 | static_check | 0.272749 | 0.214714 | 15464 | 992554 | 409600 | 0 |
| changed-small-verified-cold-0 | resource_env | 0.442034 | 0.495180 | 34156 | 6194756 | 0 | 0 |
| changed-small-verified-cold-0 | sizing_report | 0.340711 | 0.365092 | 34160 | 6194756 | 0 | 4096 |
| changed-small-verified-cold-1 | static_check | 0.169304 | 0.203512 | 15272 | 992554 | 1105920 | 0 |
| changed-small-verified-cold-1 | resource_env | 0.425514 | 0.435236 | 33880 | 6194756 | 839680 | 0 |
| changed-small-verified-cold-1 | sizing_report | 0.434890 | 0.495759 | 34212 | 6194756 | 0 | 4096 |
| changed-small-verified-cold-2 | static_check | 0.364195 | 0.323435 | 15304 | 992554 | 385024 | 0 |
| changed-small-verified-cold-2 | resource_env | 0.369984 | 0.423835 | 34288 | 6194756 | 0 | 0 |
| changed-small-verified-cold-2 | sizing_report | 0.235115 | 0.274356 | 34044 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-0 | static_check | 0.459528 | 0.237128 | 15316 | 992554 | 409600 | 0 |
| changed-small-verified-warm-0 | resource_env | 0.333087 | 0.379317 | 34228 | 6194756 | 24576 | 0 |
| changed-small-verified-warm-0 | sizing_report | 0.511784 | 0.405617 | 34120 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-1 | static_check | 0.228202 | 0.277612 | 15516 | 992554 | 266240 | 0 |
| changed-small-verified-warm-1 | resource_env | 0.243997 | 0.297438 | 33848 | 6194756 | 0 | 0 |
| changed-small-verified-warm-1 | sizing_report | 0.221798 | 0.256638 | 34088 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-2 | static_check | 0.213697 | 0.268611 | 15376 | 992554 | 503808 | 0 |
| changed-small-verified-warm-2 | resource_env | 0.482436 | 0.417042 | 33828 | 6194756 | 1376256 | 0 |
| changed-small-verified-warm-2 | sizing_report | 0.274535 | 0.308676 | 33912 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-3 | static_check | 0.122052 | 0.190061 | 15456 | 992554 | 139264 | 0 |
| changed-small-verified-warm-3 | resource_env | 0.297424 | 0.355121 | 34060 | 6194756 | 0 | 0 |
| changed-small-verified-warm-3 | sizing_report | 0.407890 | 0.442844 | 33808 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-4 | static_check | 0.323888 | 0.286180 | 15388 | 992554 | 286720 | 0 |
| changed-small-verified-warm-4 | resource_env | 0.289666 | 0.275217 | 34092 | 6194756 | 0 | 0 |
| changed-small-verified-warm-4 | sizing_report | 0.291224 | 0.304887 | 34236 | 6194756 | 0 | 4096 |
| changed-small-verified-warm-5 | static_check | 0.247069 | 0.261508 | 15200 | 992554 | 139264 | 0 |
| changed-small-verified-warm-5 | resource_env | 0.708774 | 0.525196 | 33736 | 6194756 | 0 | 0 |
| changed-small-verified-warm-5 | sizing_report | 0.454410 | 0.435885 | 33676 | 6194756 | 0 | 4096 |

| Sample | Ownership stage | Wall s | CPU s | Read bytes | Written bytes |
|---|---|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | [entrypoint] Chowning /floppy/staticfiles | 5.738958 | 0.942998 | 8196096 | 8073216 |
| baseline-large-unverified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.025025 | 0.008502 | 135168 | 0 |
| baseline-large-unverified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 2.861504 | 2.237317 | 217088 | 8192 |
| baseline-large-unverified-cold-1 | [entrypoint] Chowning /floppy/staticfiles | 2.837437 | 0.406284 | 8196096 | 8073216 |
| baseline-large-unverified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.064947 | 0.029259 | 139264 | 0 |
| baseline-large-unverified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 3.077421 | 2.594238 | 28672 | 8192 |
| baseline-large-unverified-cold-2 | [entrypoint] Chowning /floppy/staticfiles | 2.040312 | 0.280829 | 8196096 | 8073216 |
| baseline-large-unverified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.028165 | 0.017270 | 139264 | 0 |
| baseline-large-unverified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 1.501063 | 1.242035 | 5783552 | 8192 |
| baseline-large-verified-cold-0 | [entrypoint] Chowning /floppy/staticfiles | 1.060397 | 0.157980 | 8196096 | 8073216 |
| baseline-large-verified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.012617 | 0.005311 | 139264 | 0 |
| baseline-large-verified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.113989 | 1.072287 | 163840 | 8192 |
| baseline-large-verified-cold-1 | [entrypoint] Chowning /floppy/staticfiles | 0.926802 | 0.103680 | 8196096 | 8073216 |
| baseline-large-verified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.012387 | 0.005983 | 143360 | 0 |
| baseline-large-verified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 2.571119 | 1.654043 | 14831616 | 8192 |
| baseline-large-verified-cold-2 | [entrypoint] Chowning /floppy/staticfiles | 2.654563 | 0.391615 | 8196096 | 8073216 |
| baseline-large-verified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.139768 | 0.068167 | 139264 | 0 |
| baseline-large-verified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 3.365151 | 2.389146 | 155648 | 8192 |
| baseline-small-unverified-cold-0 | [entrypoint] Chowning /floppy/staticfiles | 0.635606 | 0.103238 | 8200192 | 8073216 |
| baseline-small-unverified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.010439 | 0.005887 | 139264 | 0 |
| baseline-small-unverified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.115391 | 0.864903 | 184320 | 8192 |
| baseline-small-unverified-cold-1 | [entrypoint] Chowning /floppy/staticfiles | 1.008918 | 0.117971 | 8073216 | 8073216 |
| baseline-small-unverified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.012433 | 0.007547 | 135168 | 0 |
| baseline-small-unverified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 0.845464 | 0.806686 | 28672 | 8192 |
| baseline-small-unverified-cold-2 | [entrypoint] Chowning /floppy/staticfiles | 1.389297 | 0.143842 | 5128192 | 8073216 |
| baseline-small-unverified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.005203 | 0.003283 | 0 | 0 |
| baseline-small-unverified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 0.964609 | 0.790088 | 0 | 8192 |
| baseline-small-verified-cold-0 | [entrypoint] Chowning /floppy/staticfiles | 1.942978 | 0.234785 | 8196096 | 8073216 |
| baseline-small-verified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.023072 | 0.011337 | 139264 | 0 |
| baseline-small-verified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 2.123332 | 1.469337 | 7512064 | 8192 |
| baseline-small-verified-cold-1 | [entrypoint] Chowning /floppy/staticfiles | 2.160271 | 0.240083 | 8196096 | 8073216 |
| baseline-small-verified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.020647 | 0.005107 | 139264 | 0 |
| baseline-small-verified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 2.745266 | 2.088580 | 163840 | 8192 |
| baseline-small-verified-cold-2 | [entrypoint] Chowning /floppy/staticfiles | 2.546613 | 0.522800 | 8339456 | 8073216 |
| baseline-small-verified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.014828 | 0.006719 | 131072 | 0 |
| baseline-small-verified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 1.766947 | 1.677087 | 24576 | 8192 |
| baseline-small-verified-warm-0 | [entrypoint] Chowning /floppy/staticfiles | 0.611130 | 0.111500 | 8450048 | 8073216 |
| baseline-small-verified-warm-0 | [entrypoint] Chowning /var/log/nginx | 0.008825 | 0.004160 | 147456 | 0 |
| baseline-small-verified-warm-0 | [entrypoint] Chowning /var/lib/nginx | 0.520374 | 0.508657 | 147456 | 8192 |
| baseline-small-verified-warm-1 | [entrypoint] Chowning /floppy/staticfiles | 1.349985 | 0.130061 | 8196096 | 8073216 |
| baseline-small-verified-warm-1 | [entrypoint] Chowning /var/log/nginx | 0.007842 | 0.006815 | 0 | 0 |
| baseline-small-verified-warm-1 | [entrypoint] Chowning /var/lib/nginx | 1.266958 | 1.062250 | 122880 | 8192 |
| baseline-small-verified-warm-2 | [entrypoint] Chowning /floppy/staticfiles | 1.497590 | 0.184801 | 8327168 | 8073216 |
| baseline-small-verified-warm-2 | [entrypoint] Chowning /var/log/nginx | 0.014839 | 0.003774 | 0 | 0 |
| baseline-small-verified-warm-2 | [entrypoint] Chowning /var/lib/nginx | 1.255705 | 1.100229 | 2215936 | 8192 |
| baseline-small-verified-warm-3 | [entrypoint] Chowning /floppy/staticfiles | 2.182697 | 0.208866 | 8249344 | 8073216 |
| baseline-small-verified-warm-3 | [entrypoint] Chowning /var/log/nginx | 0.034758 | 0.003962 | 131072 | 0 |
| baseline-small-verified-warm-3 | [entrypoint] Chowning /var/lib/nginx | 1.275142 | 1.114476 | 53248 | 8192 |
| baseline-small-verified-warm-4 | [entrypoint] Chowning /floppy/staticfiles | 2.200868 | 0.197013 | 8306688 | 8073216 |
| baseline-small-verified-warm-4 | [entrypoint] Chowning /var/log/nginx | 0.028846 | 0.006230 | 0 | 0 |
| baseline-small-verified-warm-4 | [entrypoint] Chowning /var/lib/nginx | 1.696450 | 1.506830 | 12288 | 8192 |
| baseline-small-verified-warm-5 | [entrypoint] Chowning /floppy/staticfiles | 2.020189 | 0.271193 | 8196096 | 8073216 |
| baseline-small-verified-warm-5 | [entrypoint] Chowning /var/log/nginx | 0.012628 | 0.004395 | 0 | 0 |
| baseline-small-verified-warm-5 | [entrypoint] Chowning /var/lib/nginx | 1.371222 | 1.200511 | 1073152 | 8192 |
| changed-custom-uid-small-verified-cold-0 | [entrypoint] Chowning /floppy/staticfiles | 2.359889 | 0.330488 | 8073216 | 8073216 |
| changed-custom-uid-small-verified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.075615 | 0.007896 | 4096 | 0 |
| changed-custom-uid-small-verified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.544091 | 1.376322 | 28672 | 8192 |
| changed-large-unverified-cold-0 | [entrypoint] Reusing image static ownership | 0.002523 | 0.001367 | 0 | 0 |
| changed-large-unverified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.012124 | 0.004375 | 4096 | 0 |
| changed-large-unverified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.962962 | 1.349698 | 5009408 | 8192 |
| changed-large-unverified-cold-1 | [entrypoint] Reusing image static ownership | 0.001479 | 0.001794 | 0 | 0 |
| changed-large-unverified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.011151 | 0.002581 | 0 | 0 |
| changed-large-unverified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 0.945359 | 0.766636 | 6631424 | 8192 |
| changed-large-unverified-cold-2 | [entrypoint] Reusing image static ownership | 0.001672 | 0.001590 | 4096 | 0 |
| changed-large-unverified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.005862 | 0.001980 | 0 | 0 |
| changed-large-unverified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 0.762371 | 0.660180 | 5726208 | 8192 |
| changed-large-verified-cold-0 | [entrypoint] Reusing image static ownership | 0.002240 | 0.003578 | 0 | 0 |
| changed-large-verified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.021988 | 0.015314 | 0 | 0 |
| changed-large-verified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.320810 | 1.271949 | 36864 | 8192 |
| changed-large-verified-cold-1 | [entrypoint] Reusing image static ownership | 0.001000 | 0.001414 | 0 | 0 |
| changed-large-verified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.007072 | 0.002894 | 4096 | 0 |
| changed-large-verified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 0.833472 | 0.714689 | 5382144 | 8192 |
| changed-large-verified-cold-2 | [entrypoint] Reusing image static ownership | 0.000898 | 0.001289 | 0 | 0 |
| changed-large-verified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.015715 | 0.010636 | 0 | 0 |
| changed-large-verified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 0.944404 | 0.783870 | 7294976 | 8192 |
| changed-small-unverified-cold-0 | [entrypoint] Reusing image static ownership | 0.001223 | 0.000881 | 0 | 0 |
| changed-small-unverified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.014968 | 0.007278 | 4096 | 0 |
| changed-small-unverified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.345604 | 1.255454 | 28672 | 8192 |
| changed-small-unverified-cold-1 | [entrypoint] Reusing image static ownership | 0.006525 | 0.003921 | 0 | 0 |
| changed-small-unverified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.031233 | 0.007903 | 8192 | 0 |
| changed-small-unverified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 1.553114 | 1.347505 | 1449984 | 8192 |
| changed-small-unverified-cold-2 | [entrypoint] Reusing image static ownership | 0.003691 | 0.004780 | 4096 | 0 |
| changed-small-unverified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.003913 | 0.001450 | 0 | 0 |
| changed-small-unverified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 1.080784 | 0.847043 | 2539520 | 8192 |
| changed-small-verified-cold-0 | [entrypoint] Reusing image static ownership | 0.001380 | 0.000646 | 0 | 0 |
| changed-small-verified-cold-0 | [entrypoint] Chowning /var/log/nginx | 0.023887 | 0.004922 | 4096 | 0 |
| changed-small-verified-cold-0 | [entrypoint] Chowning /var/lib/nginx | 1.254786 | 0.996188 | 28672 | 8192 |
| changed-small-verified-cold-1 | [entrypoint] Reusing image static ownership | 0.001517 | 0.001522 | 0 | 0 |
| changed-small-verified-cold-1 | [entrypoint] Chowning /var/log/nginx | 0.015706 | 0.003496 | 0 | 0 |
| changed-small-verified-cold-1 | [entrypoint] Chowning /var/lib/nginx | 1.426638 | 1.158237 | 872448 | 8192 |
| changed-small-verified-cold-2 | [entrypoint] Reusing image static ownership | 0.000835 | 0.001448 | 0 | 0 |
| changed-small-verified-cold-2 | [entrypoint] Chowning /var/log/nginx | 0.007954 | 0.004041 | 0 | 0 |
| changed-small-verified-cold-2 | [entrypoint] Chowning /var/lib/nginx | 0.857710 | 0.794270 | 12288 | 8192 |
| changed-small-verified-warm-0 | [entrypoint] Reusing image static ownership | 0.006417 | 0.005924 | 4096 | 0 |
| changed-small-verified-warm-0 | [entrypoint] Chowning /var/log/nginx | 0.156991 | 0.005162 | 0 | 0 |
| changed-small-verified-warm-0 | [entrypoint] Chowning /var/lib/nginx | 1.115064 | 0.934260 | 53248 | 8192 |
| changed-small-verified-warm-1 | [entrypoint] Reusing image static ownership | 0.001285 | 0.000674 | 0 | 0 |
| changed-small-verified-warm-1 | [entrypoint] Chowning /var/log/nginx | 0.013397 | 0.015084 | 0 | 0 |
| changed-small-verified-warm-1 | [entrypoint] Chowning /var/lib/nginx | 0.672050 | 0.641698 | 16384 | 8192 |
| changed-small-verified-warm-2 | [entrypoint] Reusing image static ownership | 0.003022 | 0.002766 | 0 | 0 |
| changed-small-verified-warm-2 | [entrypoint] Chowning /var/log/nginx | 0.010007 | 0.004184 | 0 | 0 |
| changed-small-verified-warm-2 | [entrypoint] Chowning /var/lib/nginx | 1.128724 | 0.890691 | 1392640 | 8192 |
| changed-small-verified-warm-3 | [entrypoint] Reusing image static ownership | 0.002228 | 0.001998 | 0 | 0 |
| changed-small-verified-warm-3 | [entrypoint] Chowning /var/log/nginx | 0.075702 | 0.011051 | 0 | 0 |
| changed-small-verified-warm-3 | [entrypoint] Chowning /var/lib/nginx | 1.072468 | 0.951762 | 12288 | 8192 |
| changed-small-verified-warm-4 | [entrypoint] Reusing image static ownership | 0.000774 | 0.000768 | 0 | 0 |
| changed-small-verified-warm-4 | [entrypoint] Chowning /var/log/nginx | 0.048944 | 0.005658 | 12288 | 0 |
| changed-small-verified-warm-4 | [entrypoint] Chowning /var/lib/nginx | 0.924529 | 0.685211 | 28672 | 10756096 |
| changed-small-verified-warm-5 | [entrypoint] Reusing image static ownership | 0.002290 | 0.001328 | 0 | 0 |
| changed-small-verified-warm-5 | [entrypoint] Chowning /var/log/nginx | 0.017066 | 0.004178 | 0 | 0 |
| changed-small-verified-warm-5 | [entrypoint] Chowning /var/lib/nginx | 1.538694 | 1.081724 | 8192 | 8192 |

| Sample | Interactive queue roundtrip ms |
|---|---:|
| baseline-small-verified-warm-0 | 321.611 |
| baseline-small-verified-warm-1 | 276.171 |
| baseline-small-verified-warm-2 | 704.866 |
| baseline-small-verified-warm-3 | 567.210 |
| baseline-small-verified-warm-4 | 386.785 |
| baseline-small-verified-warm-5 | 426.918 |
| changed-custom-uid-small-verified-cold-0 | 270.019 |
| changed-small-verified-warm-0 | 411.280 |
| changed-small-verified-warm-1 | 520.037 |
| changed-small-verified-warm-2 | 437.593 |
| changed-small-verified-warm-3 | 442.666 |
| changed-small-verified-warm-4 | 348.689 |
| changed-small-verified-warm-5 | 207.995 |
