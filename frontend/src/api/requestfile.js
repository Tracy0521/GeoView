import axios from "axios"

import global from '@/global'
import {ElMessage} from "element-plus";
import {hideFullScreenLoading} from "@/utils/loading";
export function requestfile(config) {
  const instance = axios.create({
    // timeout: 5000,
    baseURL: global.BASEURL,
    transformRequest: [function(data, headers) {
        // 去除post请求默认的Content-Type
        delete headers.post['Content-Type']
        return data
      }],
      
  })
  instance.interceptors.request.use(
    (config) => {
        config.headers.Accept = 'multipart/form-data'
        config.headers['Content-Type'] = 'multipart/form-data';
        return config
    },
    (error) => Promise.reject(error),
  )

  instance.interceptors.response.use(
    (response) => {

        if(response.data.code!==0){
            hideFullScreenLoading('#load')
            ElMessage.error(response.data.msg)
            return Promise.reject()
        }
      return response
    },
    (error) => {
      hideFullScreenLoading('#load')
      const msg = error?.response?.data?.msg || '网络异常，请检查后端服务是否启动'
      ElMessage.error(msg)
      return Promise.reject(msg)
    },
  )
  return instance(config)
}

