function goDashboard() {
  if (this.$route.path === '/dashboard') {
    this.$message.success('您已经在首页了')
  } else {
    this.$router.push('/dashboard')
  }
}

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

function goDatasetManagement() {
  if (this.$route.path === '/dataset-management') {
    this.$message.success('您已经在数据集管理页面了')
  } else {
    this.$router.push('/dataset-management')
  }
}

export { goDashboard, goDetectObjects, goHistory, goDatasetManagement }
