
import global from '@/global'
function previewOnePic(pic) {
    this.flag = 1
    this.fbflag = 1
    this.previewPic1 = global.BASEURL + pic
    this.preVisible = true;
}
function previewTwoPic(pic1, pic2) {
    this.flag = 2
    this.fbflag = 2
    this.previewPic1 = global.BASEURL + pic1
    this.previewPic2 = global.BASEURL + pic2
    this.preVisible = true
}
export { previewOnePic, previewTwoPic }
