from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Room, Topic, Message, User, StudyMatch
from .forms import RoomForm, UserForm, MyUserCreationForm

# Create your views here.

def loginPage(request):
    page = 'login'

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Username OR password is incorrect')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)

def logoutUser(request):
    logout(request)
    return redirect('home')

def registerPage(request):
    form = MyUserCreationForm()

    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'An error has occured during registration!')

    return render(request, 'base/login_register.html', {'form': form})

def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q) |
        Q(description__icontains=q)
        )
    
    topics = Topic.objects.all()[0:5]
    room_count = rooms.count()
    room_messages = Message.objects.filter(Q(room__topic__name__icontains=q))

    context = {'rooms': rooms, 'topics': topics, 'room_count': room_count, 'room_messages': room_messages}
    return render(request, 'base/home.html', context)

def room(request,pk):
    room = Room.objects.get(id=pk)
    room_messages = room.message_set.all().order_by('-created')
    participants = room.participants.all()
    if request.method == 'POST':
        message = Message.objects.create(
            user = request.user,
            room = room,
            body = request.POST.get('body')
        )
        room.participants.add(request.user)
        return redirect('room', pk=room.id) 

    context = {'room': room, 'room_messages': room_messages, 'participants': participants}
    return render(request, 'base/room.html', context)

def userProfile(request,pk):
    user = User.objects.get(id=pk)
    room_messages = user.message_set.all()
    rooms = user.room_set.all()
    topics = Topic.objects.all()
    context = {'user': user, 'rooms': rooms, 'room_messages': room_messages, 'topics': topics}
    return render(request, 'base/profile.html', context)

@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)

        Room.objects.create(
            name = request.POST.get('name'),
            description = request.POST.get('description'),
            topic = topic,
            host = request.user
        )
        return redirect('home')
    
    context = {'form': form, 'topics': topics}
    return render(request, 'base/room_form.html', context)

@login_required(login_url='login')
def updateRoom(request,pk):
    room = Room.objects.get(id=pk)
    form = RoomForm(instance=room)
    topics = Topic.objects.all()

    if request.user != room.host:
        return HttpResponse('You are not authorized!')

    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created = Topic.objects.get_or_create(name=topic_name)
        room.name = request.POST.get('name')
        room.description = request.POST.get('description')
        room.topic = topic
        room.save()
        return redirect('home')
    
    context = {'form': form, 'topics': topics, 'room': room}
    return render(request, 'base/room_form.html', context) 

@login_required(login_url='login')
def deleteRoom(request,pk):
    room = Room.objects.get(id=pk)

    if request.user != room.host:
        return HttpResponse('You are not authorized!')

    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': room})

@login_required(login_url='login')
def deleteMessage(request,pk):
    message = Message.objects.get(id=pk)

    if request.user != message.user:
        return HttpResponse('You are not authorized!')

    if request.method == 'POST':
        message.delete()
        return redirect('room', pk=message.room.id)
    return render(request, 'base/delete.html', {'obj': message})

@login_required(login_url='login')
def updateUser(request):
    user = request.user
    form = UserForm(instance=user)

    if request.method == 'POST':
        form = UserForm(request.POST,request.FILES , instance=user)
        if form.is_valid():
            form.save() 
            return redirect('user-profile', pk=user.id)

    return render(request, 'base/update-user.html', {'form': form})

def topicsPage(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    topics = Topic.objects.filter(name__icontains=q)
    context = {'topics': topics}
    return render(request, 'base/topics.html', context)

def activityPage(request):
    room_messages = Message.objects.all()
    return render(request, 'base/activity.html', {'room_messages': room_messages})


@login_required(login_url='login')
def matchPage(request):
    """显示推荐的学习伙伴列表（修复：双向排除已配对用户）"""
    
    # 获取我发出去的申请
    sent_to = StudyMatch.objects.filter(
        initiator_id=request.user
    ).values_list('receiver_id', flat=True)
    
    # 获取对方发给我的申请
    received_from = StudyMatch.objects.filter(
        receiver_id=request.user
    ).values_list('initiator_id', flat=True)
    
    # 合并排除列表（双向排除 ✅）
    excluded_ids = list(sent_to) + list(received_from) + [request.user.id]
    
    # 获取推荐用户：排除自己和已有申请的用户
    recommended_users = User.objects.exclude(id__in=excluded_ids)
    
    context = {'recommended_users': recommended_users}
    return render(request, 'base/match.html', context)


@login_required(login_url='login')
def sendMatchRequest(request):
    """发送配对申请（双向检查，防止重复申请）"""
    
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        
        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('match')
        
        # 防止自己申请自己
        if receiver == request.user:
            messages.error(request, 'You cannot send a match request to yourself')
            return redirect('match')
        
        # 检查是否已存在申请（双向检查 ✅）
        # 情况1：我已经给对方发过申请
        existing_sent = StudyMatch.objects.filter(
            initiator=request.user,
            receiver=receiver
        ).exists()
        
        # 情况2：对方已经给我发过申请
        existing_received = StudyMatch.objects.filter(
            initiator=receiver,
            receiver=request.user
        ).exists()
        
        if existing_sent or existing_received:
            messages.error(request, 'Match request already exists')
            return redirect('match')
        
        # 创建申请
        StudyMatch.objects.create(
            initiator=request.user,
            receiver=receiver
        )
        
        messages.success(request, f'Match request sent to {receiver.username}')
        return redirect('match')
    
    return redirect('match')
