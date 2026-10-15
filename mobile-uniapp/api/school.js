import { http } from '@/utils/request'

/** 学校搜索（名称 / 简称 / 别名） */
export function searchSchools(q, province, level) {
  return http({ url: '/api/v1/schools', data: { q, province, level } })
}

/** 学校详情 + 已发布红线 */
export function getSchoolDetail(id) {
  return http({ url: `/api/v1/schools/${id}` })
}

/** 设置当前用户的学校与学位 */
export function setMySchool(schoolId, degreeType) {
  return http({ url: '/api/v1/me/school', method: 'PUT', data: { schoolId, degreeType } })
}

/** 当前用户生效的红线；未命中 resolved=false */
export function getMyRule() {
  return http({ url: '/api/v1/me/rule' })
}
