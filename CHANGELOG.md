# Changelog

## [1.4.0](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.3.0...v1.4.0) (2024-11-01)


### Features

* ✨ add oss pretty endpoint ([4cf2533](https://github.com/AnzhiZhang/PeoplesDaily/commit/4cf2533b39beae2baed441e07544849c385de55a))
* ✨ delay download pdf to add pages ([67829d8](https://github.com/AnzhiZhang/PeoplesDaily/commit/67829d8de89f6f012c189ab2a0d10b4e9eb8a3a7))

## [1.3.0](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.2.0...v1.3.0) (2024-10-02)


### Features

* ✨ add bookmarks in merged PDF ([8bf09ff](https://github.com/AnzhiZhang/PeoplesDaily/commit/8bf09ffc1fc303b3af429b826ae4af35a7ab58d2))


### Bug Fixes

* 🐛 fix multiple `To` headers in email ([054e794](https://github.com/AnzhiZhang/PeoplesDaily/commit/054e7947bf2d16ff04cdff7458b584cac8e1be43))

## [1.2.0](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.1.0...v1.2.0) (2024-09-23)


### Features

* ✨ acept command line input ([c08db83](https://github.com/AnzhiZhang/PeoplesDaily/commit/c08db83b80821efb39211a1422a63b836991ea1a))
* ✨ check page count and retry ([f64ab87](https://github.com/AnzhiZhang/PeoplesDaily/commit/f64ab879f843349c9f8f55d27c621e3c2c5a15eb))
* ✨ update data path ([5b28ad5](https://github.com/AnzhiZhang/PeoplesDaily/commit/5b28ad54c57b64dc6795ea6ba7514e68173a131d))
* ✨ update oss path ([7efa84e](https://github.com/AnzhiZhang/PeoplesDaily/commit/7efa84e32e3ddca0ec23b962d3a246938168786c))
* 🔊 add log message ([140c998](https://github.com/AnzhiZhang/PeoplesDaily/commit/140c998fc5013462548267c0bd8da78655efa2f4))
* 🔊 add log message ([1b47e9c](https://github.com/AnzhiZhang/PeoplesDaily/commit/1b47e9c390348382bed53a164cc1f826fcd26ab6))
* 🔊 use logging.Logger ([4a5a021](https://github.com/AnzhiZhang/PeoplesDaily/commit/4a5a021ec1fd762b2af809cd4eb7a81a843eb2ad))


### Bug Fixes

* 🐛 fix error handing ([47fa2fb](https://github.com/AnzhiZhang/PeoplesDaily/commit/47fa2fb747b608276a181d98752d18a70a9cec79))
* 🐛 fix read and log config ([f7a1041](https://github.com/AnzhiZhang/PeoplesDaily/commit/f7a104172ef75fc4db2d3c002beabcde7348b142))
* 🔊 check before log page count ([ff6122f](https://github.com/AnzhiZhang/PeoplesDaily/commit/ff6122fe1ac49b49f5e991b689b9666c13282e53))
* 🔊 update log message ([f82ec82](https://github.com/AnzhiZhang/PeoplesDaily/commit/f82ec820a88d989c213959a462b2c3af45161674))
* 🥅 catch more errors ([eb0d78d](https://github.com/AnzhiZhang/PeoplesDaily/commit/eb0d78d9058d80a41e8e1ca9bfb22ecea7e366d6))

## [1.1.0](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.0.2...v1.1.0) (2024-09-04)


### Features

* ✨ add oss url in email ([e156be4](https://github.com/AnzhiZhang/PeoplesDaily/commit/e156be4ee391a4913a1ac82df91176440e5f9ea0))
* ✨ add upload to oss ([d5f1646](https://github.com/AnzhiZhang/PeoplesDaily/commit/d5f16469937dcc7e755b7d40fd6c2ece3f8d5741))
* ✨ allow set with_attachment in schedule task ([75c5f09](https://github.com/AnzhiZhang/PeoplesDaily/commit/75c5f095a2006399de67c5d8631fe19b061a5ef5))
* ✨ set schedule task run at 22:00 ([325c3b0](https://github.com/AnzhiZhang/PeoplesDaily/commit/325c3b0ea47260ed5047b3dac4620513910b9e7c))
* ✨ set schedule task run at 23:00 ([593e505](https://github.com/AnzhiZhang/PeoplesDaily/commit/593e50528fe114ae104261871e96037294bc315b))
* 🔇 disable pypdf warnings ([408e5ab](https://github.com/AnzhiZhang/PeoplesDaily/commit/408e5ab5ab2f682dce113254f7066526e5f6ba02))
* 🔊 update log ([39b2031](https://github.com/AnzhiZhang/PeoplesDaily/commit/39b20316e6ac13da003bc6576cb029d628cd6e33))
* 🔒️ use AuthV4 for upload to oss ([e7c65db](https://github.com/AnzhiZhang/PeoplesDaily/commit/e7c65dbbae42b54ce5b47c750f78af173ed66bf9))


### Bug Fixes

* 🐛 add with_attachment arg ([fdff31c](https://github.com/AnzhiZhang/PeoplesDaily/commit/fdff31cd1ac497dd1c62e8e32c036e9726b70ac3))
* 🐛 fix data dir ([bd850ac](https://github.com/AnzhiZhang/PeoplesDaily/commit/bd850aca78f2e9d8834be180b83e71d0f46ada97))
* 🐛 fix get oss config from environ ([2793c7b](https://github.com/AnzhiZhang/PeoplesDaily/commit/2793c7bdf1f83f6e4f4cdb78c68b62a593bb2bd0))
* 🐛 fix import path ([d0d52cf](https://github.com/AnzhiZhang/PeoplesDaily/commit/d0d52cf72e0488ffb6acc521290bb891b4304dc7))
* 🔇 log config on start ([6a9aa90](https://github.com/AnzhiZhang/PeoplesDaily/commit/6a9aa90b4b90a3de139a25131d04c34076ccc88a))

## [1.0.2](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.0.1...v1.0.2) (2024-09-01)


### Bug Fixes

* 🔊 log when email disabled ([67db9a1](https://github.com/AnzhiZhang/PeoplesDaily/commit/67db9a1fd0c7c7dd058f7fc8bfcaacc54d64cdbf))

## [1.0.1](https://github.com/AnzhiZhang/PeoplesDaily/compare/v1.0.0...v1.0.1) (2024-09-01)


### Bug Fixes

* 🐛 fix imports ([ba4a5ea](https://github.com/AnzhiZhang/PeoplesDaily/commit/ba4a5ea018a82e1913844c5f7a07ffc3a74c962f))

## 1.0.0 (2024-09-01)


### Features

* ✨ add data to GitHub outputs ([60c6c16](https://github.com/AnzhiZhang/PeoplesDaily/commit/60c6c16399e196f009240432591ebb06feab40cc))
* ✨ add schedule_task ([cc1fe0e](https://github.com/AnzhiZhang/PeoplesDaily/commit/cc1fe0e85ca68599943efc1d59c20e5b03bb7214))
* ✨ add send_email ([d34b24b](https://github.com/AnzhiZhang/PeoplesDaily/commit/d34b24be85f705c3cd00d40bdb8e9a574e49187c))
* ✨ refactor and clean ([3468c03](https://github.com/AnzhiZhang/PeoplesDaily/commit/3468c0355802ffd3efc161058b84393ff73f8d4c))
* 🔊 add email config log ([66452dc](https://github.com/AnzhiZhang/PeoplesDaily/commit/66452dc2b76698c773b63b71db5379f61bbfe904))
* **release:** add url in release body ([88f73f3](https://github.com/AnzhiZhang/PeoplesDaily/commit/88f73f3eb8cb4c49b7276648e826f60b9ca95056))


### Bug Fixes

* 👽️ update deprecated code ([7d1bb28](https://github.com/AnzhiZhang/PeoplesDaily/commit/7d1bb287f4553f6a2d2a113a07508211de89b3b0))
* 💚 fix github output multiline ([0213608](https://github.com/AnzhiZhang/PeoplesDaily/commit/02136089bb94565999fd2ffc30a33c98f9c3cf3c))
* 🩹 add EmailConfig to __all__ ([8060f1d](https://github.com/AnzhiZhang/PeoplesDaily/commit/8060f1d7187a79a41547ab235df388ece54a52c4))
* 🩹 fix args description ([d8e9f49](https://github.com/AnzhiZhang/PeoplesDaily/commit/d8e9f496454689dbb0ed273883e291da3b938a93))
* 🩹 set --write-github-output default value ([0beb521](https://github.com/AnzhiZhang/PeoplesDaily/commit/0beb521cb9c2a8dd95d6901743f585c48f71c97e))
* **time:** server time is utc time ([a186902](https://github.com/AnzhiZhang/PeoplesDaily/commit/a186902aecc1c593b6065ccdc74e3edd9aaa24ee))
