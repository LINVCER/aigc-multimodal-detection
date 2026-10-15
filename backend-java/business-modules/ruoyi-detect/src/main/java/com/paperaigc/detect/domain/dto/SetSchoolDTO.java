package com.paperaigc.detect.domain.dto;

import lombok.Data;

/** PUT /me/school 入参 */
@Data
public class SetSchoolDTO {
    private Long schoolId;
    /** bachelor / master / phd */
    private String degreeType;
}
