export default function useForm({ setData, setIsEmpty, setErrorMessage }) {

    const handleChange = (field, value) => {
        setData(prev => ({ ...prev, [field]: value }));
        setIsEmpty(prev => ({ ...prev, [field]: false }));
        setErrorMessage("");
    }

    return { handleChange };
}