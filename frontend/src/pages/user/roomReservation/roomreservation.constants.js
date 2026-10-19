export const initialForm = {
    name: "",
    program: "",
    campus: "Laguna",
    contact_number: "",
    id_number: "",
    dept: "",
    email: "",
    lrc: "",
    room: "",
    time: {start_time: "", end_time: ""}
}

export const formFields = [
    {label: "Name", name: "name"},
    {label: "Program", name: "program"},
    {label: "Contact Number", name: "contact_number"},
    {label: "Campus", name: "campus"},
    {label: "ID Number", name: "id_number"},
    {label: "Department", name: "dept"},
    {label: "Email", name: "email"},
]

export const roomSelection = {
    "LRC 1": ["Room 1", "Room 2"],
    "LRC 2": ["Room 1"],
}