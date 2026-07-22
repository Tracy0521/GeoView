import axios from "axios"

import global from '@/global'
import {hideFullScreenLoading, showFullScreenLoading} from '@/utils/loading'
import {ElMessage} from "element-plus";

export function request(config) {
  const instance = axios.create({
    baseURL:global.BASEURL
  })
    instance.interceptors.request.use(
        config=>{
            showFullScreenLoading()
            return config
        }
    )
  instance.interceptors.response.use(
    (response) => {
        hideFullScreenLoading()
      if(response.data.code!==0){
          const message=response.data.msg||'请求失败'
          ElMessage.error(message)
        return Promise.reject(new Error(message))
      }
      return response
    },
    ({ response, message }) => {
      hideFullScreenLoading()
      const errorMessage=response&&response.data&&response.data.msg
        ? response.data.msg
        : (message||'网络异常，请检查后端服务是否启动')
      ElMessage.error(errorMessage)
      return Promise.reject(new Error(errorMessage))
    },
  )
  return instance(config)
}

