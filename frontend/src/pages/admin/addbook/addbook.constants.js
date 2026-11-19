export const initialFormValues = {
    isbn: "",
    title: "",
    author: "",
    edition: "",
    description: "",
    publisher: "",
    date_acquired: "",
    accession_number: "",
    year_published: "",
    pages: "",
    tags: [],
    classification: "",
    call_number: "",
    cover_url: null,
}

export const labelToName = {
    ISBN : "isbn",
    Publisher : "publisher",
    Title : "title",
    Date_Aquired : "date_acquired",
    Accession_Number : "accession_number",
    Author : "author",
    Year_Published : "year_published",
    Edition : "edition",
    Pages : "pages",
    Description : "description",
    Tags : "tags",
    Classification : "classification",
    Call_Number : "call_number",
}

export const initialFormErrors = {
    isbn:  false,
    title : false,
    author : false,
    edition : false,
    description : false,
    publisher : false,
    date_acquired : false,
    year_published : false,
    pages : false,
    tags : false,
    classification : false,
    call_number : false
}