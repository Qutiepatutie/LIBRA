import styles from "../../../styles/adminPages/dashboard/dashboardheader.module.css" 

import CustomButton from "../../../components/ui/CustomButton.jsx"
import { Selector } from "../../../components/ui/Inputs"

import { programs } from "../../../components/auth/register/register.constants";

export default function Header({ params, setParams, setAppliedParams, appliedParams, data, loading }) {

    const isChanged = JSON.stringify(params) !== JSON.stringify(appliedParams);

    const handleChange = (param, value) => {
        setParams(prev => ({...prev, [param]: value}))
    }

    const handleApply = () => {
        setAppliedParams({ ...params });
        data(params);
    }
    
    return (
        <div className={styles.header}>
            <div className={styles.selectors}>
                <div className={styles.selector}>
                    <Selector
                        label="Item Type"
                        name="item_type"
                        placeholder="All"
                        height="1.5em"
                        value={params.item_type}
                        options={["Book", "Thesis"]}
                        onChange={(e) => handleChange(e.target.name, e.target.value)}
                        disabled={loading}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Academic Year"
                        name="academic_year"
                        placeholder="Current"
                        height="1.5em"
                        value={params.academic_year}
                        options={["2025-2026"]}
                        onChange={(e) => handleChange(e.target.name, e.target.value)}
                        disabled={loading}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Program"
                        name="program"
                        placeholder="All"
                        height="1.5em"
                        value={params.program}
                        options={programs}
                        onChange={(e) => handleChange(e.target.name, e.target.value)}
                        disabled={loading}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Semester Term"
                        name="semester"
                        placeholder="Current"
                        height="1.5em"
                        value={params.semester}
                        options={["1", "2"]}
                        onChange={(e) => handleChange(e.target.name, e.target.value)}
                        disabled={loading}
                    />
                </div>
            </div>
            
            <div className={styles.filters}>
                <button
                    className={ params.range === "day" ? styles.active : ""}
                    onClick={() => {
                        handleChange("range", "day")
                    }}
                    disabled={loading}
                >
                    Day
                </button>
                <button
                    className={ params.range === "week" ? styles.active : ""}
                    onClick={() => {
                        handleChange("range", "week")
                    }}
                    disabled={loading}
                >
                    Week
                </button>
                <button
                    className={ params.range === "semester"? styles.active : ""}
                    onClick={() => {
                        handleChange("range", "semester")
                    }}
                    disabled={loading}
                >
                    Semester
                </button>
                <button
                    className={ params.range === "year" ? styles.active : ""}
                    onClick={() => {
                        handleChange("range", "year")
                    }}
                    disabled={loading}
                >
                    Year
                </button>
            </div>

            <div className={styles.buttons}>
                <CustomButton
                    value="Apply Filters"
                    disabled={!isChanged || loading}
                    onClick={() => handleApply()}
                />

                {isChanged && (
                    <CustomButton
                        value="Reset"
                        action="clear"
                        onClick={() => {
                            setParams(appliedParams);
                        }}
                        disabled={loading}
                    />
                )}
                
            </div>
        </div>
    ) 
}