function goDetectObjects() {
  if (this.$route.path === '/detectobjects') {
    this.$message.success('您已经在目标检测页面了')
  } else {
    this.$router.push('/detectobjects')
  }
}

function goHistory() {
  if (this.$route.path === '/history') {
    this.$message.success('您已经在历史记录页面了')
  } else {
    this.$router.push('/history')
  }
}

export { goDetectObjects, goHistory }
