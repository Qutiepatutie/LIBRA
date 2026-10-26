export default function useForm({ setData, setIsEmpty, setErrorMessage }) {

    const handleChange = (field, value) => {
        setData(prev => ({ ...prev, [field]: value.trim() }));
        setIsEmpty(prev => ({ ...prev, [field]: false }));
        setErrorMessage("");
    }

    return { handleChange };
}